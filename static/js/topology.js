let network = null;
let topologyData = null;
let connectMode = false;
let connectFromNode = null;
let temp_connect = null;




// Load topology data from API
async function loadTopology() {
    try {
        const response = await fetch('/api/topology');
        if (!response.ok) {
            throw new Error('Failed to load topology');
        }
        
        topologyData = await response.json();
        updateTopologyInfo();
        renderTopology();
        restoreLiqoConnections();
    } catch (error) {
        console.error('Error loading topology:', error);
        alert('Failed to load topology: ' + error.message);
    }
}

// Update topology information in sidebar
function updateTopologyInfo() {
    document.getElementById('topology-name').textContent = topologyData.name;
    document.getElementById('node-count').textContent = topologyData.nodes.length;
    document.getElementById('link-count').textContent = topologyData.links.length;
    
    const runningCount = topologyData.nodes.filter(n => 
        n.container && n.container.status === 'running'
    ).length;
    document.getElementById('running-count').textContent = runningCount;
}

// Calculate positions based on node type
function calculateNodePositions(nodes) {
    const positions = {};
    
    // Separate nodes by type
    const routers = nodes.filter(n => n.type === 'router');
    const switches = nodes.filter(n => n.type === 'switch');
    const k3sNodes = nodes.filter(n => n.type === 'k3s-node' || n.id.includes('serf'));
    const others = nodes.filter(n => !routers.includes(n) && !switches.includes(n) && !k3sNodes.includes(n));
    
    // Center routers
    routers.forEach((router, index) => {
        positions[router.id] = {
            x: index * 300 - ((routers.length - 1) * 150),
            y: 0
        };
    });
    
    
    switches.forEach((sw, index) => {
        positions[sw.id] = {
            x: index * 400 - ((switches.length - 1) * 200),
            y: 250
        };
    });
    
    
    const radius = 500;
    const angleStep = (2 * Math.PI) / k3sNodes.length;
    
    k3sNodes.forEach((node, index) => {
        const angle = index * angleStep - Math.PI / 2; 
        positions[node.id] = {
            x: Math.cos(angle) * radius,
            y: Math.sin(angle) * radius + 200
        };
    });
    
    
    others.forEach((node, index) => {
        positions[node.id] = {
            x: (index - others.length / 2) * 150,
            y: -300
        };
    });
    
    return positions;
}


function getNodeColor(node, isRunning, hasMonitoring) {
    
    if (node.type === 'router') {
        return { background: '#FF6B6B', border: '#C0392B' };
    }
    
    
    if (node.type === 'switch') {
        return { background: '#5DADE2', border: '#2E86C1' };
    }
    
    
    if (node.type === 'k3s-node' || node.id.includes('serf')) {
        if (!isRunning) {
            return { background: '#666666', border: '#444444' }; 
        } else if (hasMonitoring) {
            return { background: '#4CAF50', border: '#45a049' };
        } else {
            return { background: '#FFA500', border: '#FF8C00' }; 
        }
    }
    
    // Default
    return { background: '#97C2FC', border: '#2B7CE9' };
}

// Get icon for node type
// function getNodeIcon(node) {
//     if (node.type === 'router') {
//         nodeConfig.shape = 'image';
//         nodeConfig.image = 'https://cdn-icons-png.flaticon.com/128/1705/1705312.png'; // Router icon
//         nodeConfig.size = 40;
//     }
    
//     if (node.type === 'generic-node' && node.id.includes('switch')) {
//         return {
//             face: 'FontAwesome',
//             code: '\uf1e6', // fa-network-wired
//             size: 50,
//             color: '#FFFFFF'
//         };
//     }
    
//     if (node.type === 'k3s-node' || node.id.includes('serf')) {
//         return {
//             face: 'FontAwesome',
//             code: '\uf233', // fa-server
//             size: 50,
//             color: '#425df4b0'
//         };
//     }
    
//     return null;
// }

// Render the topology using vis.js
function renderTopology() {
    const container = document.getElementById('topology-network');
    
    // Calculate positions
    const positions = calculateNodePositions(topologyData.nodes);
    
    // Prepare nodes for vis.js
    const nodes = topologyData.nodes.map(node => {
        const isRunning = node.container && node.container.status === 'running';
        const hasMonitoring = node.container && Object.keys(node.container.urls).length > 0;
        
        const nodeConfig = {
            id: node.id,
            label: node.label,
            title: `${node.label}\nType: ${node.type}\nStatus: ${node.container?.status || 'unknown'}`,
            font: { 
                color: '#2C3E50',      
                size: 16,              
                face: 'Arial',
                bold: {
                    color: '#1A252F',  
                    size: 16
                },
                background: 'rgba(255, 255, 255, 0.8)',  
                strokeWidth: 2,        
                strokeColor: '#FFFFFF'
            },
            data: node,
            x: positions[node.id]?.x || 0,
            y: positions[node.id]?.y || 0
        };
        
        // Configure based on node type
        if (node.type === 'router') {
            nodeConfig.shape = 'image';
            nodeConfig.image = '/images/router.png'; // Router
            nodeConfig.size = 35;
            nodeConfig.color = {
                border: '#000000',
                background: '#FFFFFF'
            };
            nodeConfig.borderWidth = 3;
            nodeConfig.shapeProperties = {
                useBorderWithImage: true
            };
            
        } else if (node.type === 'generic-node' && node.id.includes('switch')) {
            nodeConfig.shape = 'image';
            nodeConfig.image = '/images/switch_2.png'; // Switch
            nodeConfig.size = 35;
            nodeConfig.color = {
                border: '#000000',
                background: '#FFFFFF'
            };
            nodeConfig.borderWidth = 3;
            nodeConfig.shapeProperties = {
                useBorderWithImage: true
            };
            
        } else if (node.type === 'k3s-node' || node.id.includes('serf')) {
            nodeConfig.shape = 'image';
            nodeConfig.image = '/images/server.png'; // Server
            nodeConfig.size = 35;
            
            // Color border based on monitoring status
            if (!isRunning) {
                nodeConfig.color = {
                    border: '#666666', // Gray - not running
                    background: '#FFFFFF'
                };
            } else if (hasMonitoring) {
                nodeConfig.color = {
                    border: '#4CAF50', // Green - monitoring active
                    background: '#FFFFFF'
                };
            } else {
                nodeConfig.color = {
                    border: '#FFA500', // Orange - running but no monitoring
                    background: '#FFFFFF'
                };
            }
            nodeConfig.borderWidth = 4;
            nodeConfig.shapeProperties = {
                useBorderWithImage: true
            };
            
        } else {
            // Default/other nodes
            nodeConfig.shape = 'box';
            nodeConfig.color = getNodeColor(node, isRunning, hasMonitoring);
        }
        
        return nodeConfig;
    });
    
    
    // Prepare edges for vis.js
    const edges = topologyData.links.map((link, index) => ({
        id: index,
        from: link.source,
        to: link.target,
        arrows: { 
            to: { 
                enabled: false 
            } 
        },
        color: { 
            color: '#7F8C8D',      // Darker gray
            highlight: '#3498DB',   // Blue when hovered
            hover: '#3498DB'
        },
        smooth: { 
            type: 'continuous',
            roundness: 0.2 
        },
        width: 3,                   // Thicker lines
        hoverWidth: 5,              // Even thicker on hover
        selectionWidth: 5,
        shadow: {                   // Add shadow to links
            enabled: true,
            color: 'rgba(0,0,0,0.2)',
            size: 5,
            x: 2,
            y: 2
        }
    }));
    
    // Create a network
    const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };
    
    const options = {
        physics: {
            enabled: true,
            stabilization: {
                enabled: true,
                iterations: 200,
                fit: true
            },
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.1,
                springLength: 200,
                springConstant: 0.04,
                damping: 0.95,
                avoidOverlap: 0.2
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            dragNodes: true,
            dragView: true,
            zoomView: true
        },
        layout: {
            improvedLayout: true
        }
    };
    
    network = new vis.Network(container, data, options);
    
    // Add click event listener MODIFIED BY DANK
    network.on('click', async function(params) {
        if (params.nodes.length > 0) {
            const clickedNode = params.nodes[0];
            
            // Check if we are in pod creation mode
            if (podCreationMode && podCreationSourceNode && clickedNode !== podCreationSourceNode) {
                
                // Validate destination is a K3s node
                const destNode = topologyData.nodes.find(n => n.id === clickedNode);
                if (!destNode || !(destNode.type === 'k3s-node' || destNode.id.includes('serf'))) {
                    alert('Destination must be a K3s node (serf node)');
                    podCreationMode = false;
                    podCreationSourceNode = null;
                    return;
                }
                
                // Check if Liqo connection exists between these nodes
                const connectionExists = await checkLiqoConnectionExists(podCreationSourceNode, clickedNode);
                if (!connectionExists) {
                    alert(`❌ No Liqo connection exists between ${podCreationSourceNode} and ${clickedNode}`);
                    podCreationMode = false;
                    podCreationSourceNode = null;
                    return;
            }
            
                // Open modal with pre-selected destination
                openVirtualPodModalWithDestination(podCreationSourceNode, clickedNode);
                
                // Reset pod creation mode
                podCreationMode = false;
                podCreationSourceNode = null;
                return;
            }


            // Check if we are in connect mode
            if (connectMode && connectFromNode && clickedNode !== connectFromNode) {

                // Validate destination is also a K3s node
                const destNode = topologyData.nodes.find(n => n.id === clickedNode);
                if (!destNode || !(destNode.type === 'k3s-node' || destNode.id.includes('serf'))) {
                    alert('Liqo connections can only be made between K3s nodes (serf nodes)');
                    connectMode = false;
                    connectFromNode = null;
                    return;
                }


                // Add dotted edge
                const edgeId = `temp-${Date.now()}`;

                // Add blinking grey dotted edge first
                network.body.data.edges.add({
                    id: edgeId,
                    from: connectFromNode,
                    to: clickedNode,
                    dashes: true,
                    arrows: { to: false },
                    color: {
                        color: '#7F8C8D',
                        hover: '#7F8C8D',
                        highlight: '#7F8C8D'
                    },
                    width: 2
                });

                showClusterPopupAboveNode(connectFromNode, clickedNode, false);
                temp_connect = connectFromNode

                // ----- BLINKING EFFECT -----
                let visible = true;

                const blinkInterval = setInterval(() => {
                    visible = !visible;

                    network.body.data.edges.update({
                        id: edgeId,
                        hidden: !visible
                    });
                }, 400); // blink speed

                // ----- AFTER 10s -> make permanent green -----
                setTimeout(() => {
                    clearInterval(blinkInterval);

                    network.body.data.edges.update({
                        id: edgeId,
                        hidden: false,
                        color: {
                            color: '#27ae60',
                            hover: '#27ae60',
                            highlight: '#27ae60'
                        }, 
                        dashes: true,
                        width: 3
                    });

                    showClusterPopupAboveNode(temp_connect, clickedNode, true);
                    saveLiqoConnection(temp_connect, clickedNode);
                    // Add node to sidebar
                }, 10000);

                // Reset connect mode
                connectMode = false;
                connectFromNode = null;
                return; // Skip normal click behavior
            }

            // Normal node click handling
            const node = topologyData.nodes.find(n => n.id === clickedNode);
            handleNodeClick(node);
        }
    });
    
    // Fit network after stabilization
    network.once('stabilizationIterationsDone', function() {
        network.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    });
    // Start node load monitoring
    startNodeLoadMonitoring();
}

// Handle node click event
// Handle node click event
async function handleNodeClick(node) {
    const detailsDiv = document.getElementById('node-details');
    
    if (node.type === 'router' || node.type === 'switch') {
        detailsDiv.innerHTML = `
            <h4>${node.label}</h4>
            <p><strong>Type:</strong> ${node.type}</p>
            <p><strong>Kind:</strong> ${node.kind}</p>
            <p class="info">This is a network device (no monitoring available)</p>
        `;
        return;
    }
    
    if (!node.container || node.container.status !== 'running') {
        detailsDiv.innerHTML = `
            <h4>${node.label}</h4>
            <p class="error">Container not running</p>
            <p><strong>Type:</strong> ${node.type}</p>
            <p><strong>Kind:</strong> ${node.kind}</p>
        `;
        return;
    }
    
    const urls = node.container.urls;
    
    detailsDiv.innerHTML = `
        <h4>${node.label}</h4>
        <p>Loading cluster information...</p>
    `;
    
    try {
        const response = await fetch(`/api/node/${node.id}/cluster-info`);
        const clusterInfo = await response.json();
        
        if (response.ok) {
            await displayClusterInfo(node, urls, clusterInfo); // ✅ await added
        } else {
            displayBasicInfo(node, urls, clusterInfo.error);
        }
    } catch (error) {
        displayBasicInfo(node, urls, 'Failed to load cluster info');
    }
}

async function displayClusterInfo(node, urls, clusterInfo) {
    const detailsDiv = document.getElementById('node-details');
    
    let resourcesHTML = '<p class="hint">Not available</p>';
    try {
        const configResponse = await fetch(`/api/node/${node.id}/emulation-config`);
        if (configResponse.ok) {
            const configData = await configResponse.json();
            resourcesHTML = configData.resources.map(r => `
                <p>💻 <strong>CPU:</strong> ${r.cpu}</p>
                <p>🧠 <strong>Memory:</strong> ${r.memory}</p>
            `).join('');
        }
    } catch (error) {
        console.error('Error fetching emulation config:', error);
    }

    let linksHTML = '';
    if (urls.grafana || urls.monitoring) {
        const grafanaUrl = urls.grafana || urls.monitoring;
        linksHTML += `<a href="${grafanaUrl}" target="_blank" class="link-btn grafana-btn">📈 Open Dashboard</a>`;
    }
    
    // Build namespace and pod list with metrics buttons
    const skipNamespaces = ['kube-system', 'kube-public', 'kube-node-lease', 'default'];
    let namespacesHTML = '';
    for (const ns of clusterInfo.namespaces) {
        if (skipNamespaces.includes(ns)) continue;
        
        const pods = clusterInfo.pods_by_namespace[ns] || [];
        
        namespacesHTML += `
            <div class="namespace-section">
                <h6 onclick="toggleSection('pods-${ns}-${node.id}')" style="cursor: pointer;">
                    📦 ${ns} (${pods.length} pods) ▼
                </h6>
                <div id="pods-${ns}-${node.id}" class="pod-list" style="display: none;">
        `;
        
        for (const pod of pods) {
            namespacesHTML += `
                <div class="pod-item">
                    <div class="pod-name-row">
                        <span class="pod-name">${pod.name}</span>
                    </div>
                    <div class="pod-controls-row">
                        <span class="pod-status status-${pod.status.toLowerCase()}">${pod.status}</span>
                        <div class="pod-metrics-buttons">
                            <button class="pod-metric-btn" onclick="openPodMetricsModal('${node.id}', '${ns}', '${pod.name}', 'cpu')" title="CPU">📊</button>
                            <button class="pod-metric-btn" onclick="openPodMetricsModal('${node.id}', '${ns}', '${pod.name}', 'memory')" title="Memory">💾</button>
                            <button class="pod-metric-btn" onclick="openPodMetricsModal('${node.id}', '${ns}', '${pod.name}', 'psi')" title="PSI">⚡</button>
                            <button class="pod-metric-btn" onclick="openPodMetricsModal('${node.id}', '${ns}', '${pod.name}', 'power')" title="Power">🔋</button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        namespacesHTML += `
                </div>
            </div>
        `;
    }

    if (!namespacesHTML) {
        namespacesHTML = '<p class="hint">No workload namespaces found</p>';
    }
    
    // ✅ NOW ASYNC - await getLiqoNodesForCluster
    let nodesHTML = '<ul class="node-list">';
    for (const n of clusterInfo.nodes) {
        const nodeType = n.type === 'kwok' ? '🔷 KWOK' : '⚙️ Real';
        nodesHTML += `<li>${nodeType} <strong>${n.name}</strong> (${n.status})</li>`;
    }

    const liqoNodes = await getLiqoNodesForCluster(node.id); // ✅ await added

    liqoNodes.forEach(name => {
        nodesHTML += `<li class="liqo-node">${name} (virtual)</li>`;
    });

    nodesHTML += '</ul>';
    
    detailsDiv.innerHTML = `
        <h4>${node.label}</h4>
        <p><strong>Status:</strong> <span class="status-running">Running</span></p>
        <p><strong>Type:</strong> ${node.type}</p>
        
        <div class="cluster-section">
            <h5>📦 K3s Cluster</h5>
            <p><strong>Total Pods:</strong> ${clusterInfo.total_pods}</p>
            <p><strong>Namespaces:</strong> ${clusterInfo.namespaces.length}</p>
            <p><strong>Nodes:</strong> ${clusterInfo.nodes.length}</p>
        </div>
        <div class="cluster-section">
            <h5>⚙️ Emulation Resources</h5>
            ${resourcesHTML}
        </div>
        
        <div class="cluster-section collapsible">
            <h5 onclick="toggleSection('namespaces-${node.id}')" style="cursor: pointer;">
                📁 Namespaces & Pods ▼
            </h5>
            <div id="namespaces-${node.id}" class="collapsible-content">
                ${namespacesHTML}
            </div>
        </div>
        
        <div class="cluster-section collapsible">
            <h5 onclick="toggleSection('nodes-${node.id}')" style="cursor: pointer;">
                🖥️ Cluster Nodes ▼
            </h5>
            <div id="nodes-${node.id}" class="collapsible-content">
                ${nodesHTML}
            </div>
        </div>
        
        <div class="metrics-buttons">
            <strong>View Metrics:</strong>
            <div class="button-group">
                <button class="metric-btn cpu-btn" onclick="openMetricsModal('${node.id}', 'cpu')">📊 CPU</button>
                <button class="metric-btn memory-btn" onclick="openMetricsModal('${node.id}', 'memory')">💾 Memory</button>
                <button class="metric-btn psi-btn" onclick="openMetricsModal('${node.id}', 'psi')">⚡ PSI</button>
                <button class="metric-btn power-btn" onclick="openMetricsModal('${node.id}', 'power')">🔋 Power</button>
            </div>
        </div>

        <div class="links-section">
            <strong>Monitoring:</strong>
            <div class="links">${linksHTML}</div>
        </div>
    `;
}

function displayBasicInfo(node, urls, error) {
    const detailsDiv = document.getElementById('node-details');
    
    let linksHTML = '';
    if (urls.grafana || urls.monitoring) {
        const grafanaUrl = urls.grafana || urls.monitoring;
        linksHTML += `<a href="${grafanaUrl}" target="_blank" class="link-btn grafana-btn">📈 Open Dashboard</a>`;
    }
    
    detailsDiv.innerHTML = `
        <h4>${node.label}</h4>
        <p><strong>Status:</strong> <span class="status-running">Running</span></p>
        <p><strong>Type:</strong> ${node.type}</p>
        <p class="warning">Cluster info unavailable: ${error}</p>
        
        <div class="links-section">
            <strong>Monitoring:</strong>
            <div class="links">${linksHTML}</div>
        </div>
    `;
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section.style.display === 'none') {
        section.style.display = 'block';
    } else {
        section.style.display = 'none';
    }
}

// Refresh topology
function refreshTopology() {
    document.getElementById('refresh-btn').textContent = '⏳ Refreshing...';
    loadTopology().then(() => {
        document.getElementById('refresh-btn').textContent = '🔄 Refresh';
    });
}


// Modal functions
// function openMetricsModal(nodeName, metricType) {
//     const modal = document.getElementById('metrics-modal');
//     const title = document.getElementById('modal-title');
    
//     // Update modal title
//     title.textContent = `${nodeName} - ${metricType.toUpperCase()} Metrics`;
    
//     // Show modal
//     modal.style.display = 'block';
    
//     // Create dummy chart for testing
//     createDummyChart(metricType);

// }

function closeMetricsModal() {
    const modal = document.getElementById('metrics-modal');
    modal.style.display = 'none';
    
    // Stop auto-refresh when closing modal
    stopAutoRefresh();
    const checkbox = document.getElementById('auto-refresh-toggle');
    if (checkbox) {
        checkbox.checked = false;
    }
    
    // Reset pod metrics flag
    window.isPodMetrics = false;
}





// Modal functions
function openMetricsModal(nodeName, metricType) {
    const modal = document.getElementById('metrics-modal');
    const title = document.getElementById('modal-title');
    
    // Stop any existing auto-refresh first
    stopAutoRefresh();

    // Update modal title
    title.textContent = `${nodeName} - ${metricType.toUpperCase()} Metrics`;
    
    modal.style.display = 'block';

    // Store current node and metric for refresh
    window.currentModalNode = nodeName;
    window.currentModalMetric = metricType;
    window.currentTimeWindow = '5m';  // Default

    // Add time range selector
    addTimeRangeSelector();
    // Enable auto-refresh by default
    setTimeout(() => {
        const checkbox = document.getElementById('auto-refresh-toggle');
        if (checkbox) {
            checkbox.checked = true;
            toggleAutoRefresh();
        }
    }, 100);
    // Load real chart data
    loadMetricsChart(nodeName, metricType, '5m');
}

// Pod metrics modal
function openPodMetricsModal(nodeName, namespace, podName, metricType) {
    const modal = document.getElementById('metrics-modal');
    const title = document.getElementById('modal-title');
    
    // Stop any existing auto-refresh first
    stopAutoRefresh();
    
    // Reset and set pod context BEFORE anything else
    window.isPodMetrics = true;
    window.currentModalNode = nodeName;
    window.currentModalNamespace = namespace;
    window.currentModalPod = podName;
    window.currentModalMetric = metricType;
    window.currentTimeWindow = '5m';
    
    // Update modal title
    title.textContent = `${podName} (${namespace}) - ${metricType.toUpperCase()}`;
    
    // Show modal
    modal.style.display = 'block';
    
    // Add time range selector
    addTimeRangeSelector();
    
    // Load pod metrics FIRST
    loadPodMetricsChart(nodeName, namespace, podName, metricType, '5m');
    
    // Enable auto-refresh AFTER initial load
    setTimeout(() => {
        const checkbox = document.getElementById('auto-refresh-toggle');
        if (checkbox) {
            checkbox.checked = true;
            toggleAutoRefresh();
        }
    }, 500);  // Increased delay to ensure chart loads first
}

async function loadPodMetricsChart(nodeName, namespace, podName, metricType, window = '5m') {
    try {
        const response = await fetch(`/api/node/${nodeName}/pod/${namespace}/${podName}/timeseries?metric=${metricType}&window=${window}`);
        const data = await response.json();
        
        if (response.ok && data.timestamps && data.values) {
            createPodChart(data, metricType);
        } else {
            console.error('No pod data available:', data.error);
            showChartError('No pod metric data available');
        }
    } catch (error) {
        console.error('Error loading pod metrics:', error);
        showChartError('Failed to load pod metrics');
    }
}

function createPodChart(data, metricType) {
    const ctx = document.getElementById('metrics-chart').getContext('2d');
    
    // Convert timestamps to labels
    const labels = data.timestamps.map(ts => {
        const date = new Date(ts * 1000);
        return date.toLocaleTimeString();
    });
    
    const dataset = {
        label: `Pod ${metricType.toUpperCase()}`,
        data: data.values,
        borderColor: getMetricColor(metricType),
        backgroundColor: getMetricColor(metricType, 0.1),
        tension: 0.4,
        fill: true
    };
    
    // If chart exists, update it
    if (window.currentChart) {
        window.currentChart.data.labels = labels;
        window.currentChart.data.datasets = [dataset];
        window.currentChart.update('none');
    } else {
        // Create new chart
        window.currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [dataset]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    }
}

async function loadMetricsChart(nodeName, metricType, window = '5m') {
    try {
        const response = await fetch(`/api/node/${nodeName}/timeseries?metric=${metricType}&window=${window}`);
        const data = await response.json();
        
        if (response.ok && data.datasets) {
            createChart(data, metricType);
        } else {
            console.error('No data available:', data.error);
            showChartError('No metric data available');
        }
    } catch (error) {
        console.error('Error loading metrics:', error);
        showChartError('Failed to load metrics');
    }
}

function createChart(data, metricType) {
    const ctx = document.getElementById('metrics-chart').getContext('2d');
    
    // Prepare datasets
    const datasets = [];
    let labels = [];
    
    // Add emulation data if available
    if (data.datasets.emulation_node) {
        const emulationData = data.datasets.emulation_node;
        labels = emulationData.timestamps.map(ts => {
            const date = new Date(ts * 1000);
            return date.toLocaleTimeString();
        });
        
        datasets.push({
            label: `Emulation ${metricType.toUpperCase()}`,
            data: emulationData.values,
            borderColor: getMetricColor(metricType),
            backgroundColor: getMetricColor(metricType, 0.1),
            tension: 0.4,
            fill: true
        });
    }
    
    // Add real data if available
    if (data.datasets.real_node) {
        const realData = data.datasets.real_node;
        
        datasets.push({
            label: `Real ${metricType.toUpperCase()}`,
            data: realData.values,
            borderColor: getRealMetricColor(metricType),
            backgroundColor: getRealMetricColor(metricType, 0.1),
            tension: 0.4,
            fill: false,
            borderDash: [5, 5]
        });
    }
    
    // If chart exists, update it instead of recreating
    if (window.currentChart) {
        window.currentChart.data.labels = labels;
        window.currentChart.data.datasets = datasets;
        window.currentChart.update('none'); // 'none' disables animation
    } else {
        // Create new chart only if it doesn't exist
        window.currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false, // Disable initial animation
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    }
}

function getMetricColor(metricType, alpha = 1) {
    const colors = {
        'cpu': `rgba(52, 152, 219, ${alpha})`,
        'memory': `rgba(26, 188, 156, ${alpha})`,
        'psi': `rgba(155, 89, 182, ${alpha})`,
        'power': `rgba(243, 156, 18, ${alpha})`
    };
    return colors[metricType] || `rgba(52, 152, 219, ${alpha})`;
}

function getRealMetricColor(metricType, alpha = 1) {
    const colors = {
        'cpu': `rgba(231, 76, 60, ${alpha})`,     // Red for real data
        'memory': `rgba(192, 57, 43, ${alpha})`,
        'psi': `rgba(230, 126, 34, ${alpha})`,    // Orange for real data
        'power': `rgba(192, 57, 43, ${alpha})`    // Dark red for real data
    };
    return colors[metricType] || `rgba(231, 76, 60, ${alpha})`;
}

function showChartError(message) {
    const canvas = document.getElementById('metrics-chart');
    const parent = canvas.parentElement;
    parent.innerHTML = `<p style="text-align: center; color: #e74c3c; padding: 2rem;">${message}</p>`;
}

function addTimeRangeSelector() {
    const modalBody = document.querySelector('.modal-body');
    
    // Check if selector already exists
    let selector = document.getElementById('time-range-selector');
    if (!selector) {
        selector = document.createElement('div');
        selector.id = 'time-range-selector';
        selector.className = 'time-range-selector';
        modalBody.insertBefore(selector, modalBody.firstChild);
    }
    
    selector.innerHTML = `
        <div class="time-controls">
            <div class="time-buttons">
                <button class="time-btn active" onclick="changeTimeRange('5m')">5 min</button>
                <button class="time-btn" onclick="changeTimeRange('15m')">15 min</button>
                <button class="time-btn" onclick="changeTimeRange('1h')">1 hour</button>
                <button class="time-btn" onclick="changeTimeRange('2h')">2 hours</button>
            </div>
            <div class="refresh-controls">
                <label class="refresh-toggle">
                    <input type="checkbox" id="auto-refresh-toggle" onchange="toggleAutoRefresh()">
                    <span>Auto-refresh (5s)</span>
                </label>
                <span id="refresh-indicator" class="refresh-indicator"></span>
            </div>
        </div>
    `;
}

function changeTimeRange(timeWindow) {
    window.currentTimeWindow = timeWindow;
    
    // Update active button
    document.querySelectorAll('.time-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    
    // Reload chart based on context (pod or node)
    if (window.isPodMetrics && window.currentModalPod) {
        loadPodMetricsChart(
            window.currentModalNode,
            window.currentModalNamespace,
            window.currentModalPod,
            window.currentModalMetric,
            timeWindow
        );
    } else {
        loadMetricsChart(window.currentModalNode, window.currentModalMetric, timeWindow);
    }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh-toggle');
    const indicator = document.getElementById('refresh-indicator');
    
    if (checkbox.checked) {
        // Start auto-refresh
        indicator.textContent = '🔄';
        indicator.classList.add('active');
        startAutoRefresh();
    } else {
        // Stop auto-refresh
        indicator.textContent = '';
        indicator.classList.remove('active');
        stopAutoRefresh();
    }
}

function startAutoRefresh() {
    // Clear any existing interval
    if (window.refreshInterval) {
        clearInterval(window.refreshInterval);
    }
    
    // Set new interval (5 seconds)
    window.refreshInterval = setInterval(() => {
        const indicator = document.getElementById('refresh-indicator');
        indicator.classList.add('refreshing');
        
        // Check if pod or node metrics
        if (window.isPodMetrics && window.currentModalPod) {
            loadPodMetricsChart(
                window.currentModalNode,
                window.currentModalNamespace,
                window.currentModalPod,
                window.currentModalMetric,
                window.currentTimeWindow || '5m'
            ).then(() => {
                setTimeout(() => {
                    indicator.classList.remove('refreshing');
                }, 500);
            });
        } else if (window.currentModalNode && window.currentModalMetric) {
            loadMetricsChart(
                window.currentModalNode, 
                window.currentModalMetric, 
                window.currentTimeWindow || '5m'
            ).then(() => {
                setTimeout(() => {
                    indicator.classList.remove('refreshing');
                }, 500);
            });
        }
    }, 5000);  // 5 seconds
}


function stopAutoRefresh() {
    if (window.refreshInterval) {
        clearInterval(window.refreshInterval);
        window.refreshInterval = null;
    }
}

// Node load monitoring
function startNodeLoadMonitoring() {
    // Initial load
    updateNodeColors();
    
    // Poll every 10 seconds
    if (window.nodeLoadInterval) {
        clearInterval(window.nodeLoadInterval);
    }
    
    window.nodeLoadInterval = setInterval(() => {
        updateNodeColors();
    }, 10000);
}

async function updateNodeColors() {
    try {
        const response = await fetch('/api/nodes/current-load');
        const data = await response.json();
        
        if (response.ok && data.node_loads) {
            applyNodeColors(data.node_loads);
        }
    } catch (error) {
        console.error('Error fetching node loads:', error);
    }
}

function applyNodeColors(nodeLoads) {
    if (!network) return;
    
    const nodes = network.body.data.nodes;
    const updates = [];
    
    nodes.forEach(node => {
        const nodeData = node.data;
        
        // Only update K3s nodes (not routers/switches)
        if (nodeData && (nodeData.type === 'k3s-node' || nodeData.id.includes('serf'))) {
            const loadInfo = nodeLoads[nodeData.id];
            
            if (loadInfo) {
                const borderColor = getBorderColorFromLoad(loadInfo.color);
                
                updates.push({
                    id: node.id,
                    color: {
                        border: borderColor,
                        background: '#FFFFFF'
                    },
                    borderWidth: 4
                });
            }
        }
    });
    
    // Update all nodes at once
    if (updates.length > 0) {
        nodes.update(updates);
    }
}

function getBorderColorFromLoad(colorCategory) {
    const colors = {
        'green': '#4CAF50',
        'amber': '#FFA500',
        'red': '#e74c3c'
    };
    return colors[colorCategory] || '#666666';
}


// System status monitoring
function startSystemStatusMonitoring() {
    // Initial load
    updateSystemStatus();
    
    // Poll every 5 seconds
    if (window.systemStatusInterval) {
        clearInterval(window.systemStatusInterval);
    }
    
    window.systemStatusInterval = setInterval(() => {
        updateSystemStatus();
    }, 5000);
}

async function updateSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        if (response.ok) {
            // Update CPU
            const cpuEl = document.getElementById('host-cpu');
            cpuEl.textContent = `${data.cpu.percent}% (${data.cpu.cores} cores)`;
            cpuEl.className = 'status-value ' + getStatusClass(data.cpu.percent);
            
            // Update RAM
            const ramEl = document.getElementById('host-ram');
            ramEl.textContent = `${data.memory.percent}% (${data.memory.used_gb}/${data.memory.total_gb} GB)`;
            ramEl.className = 'status-value ' + getStatusClass(data.memory.percent);
            
            // Update Disk
            const diskEl = document.getElementById('host-disk');
            diskEl.textContent = `${data.disk.percent}% (${data.disk.used_gb}/${data.disk.total_gb} GB)`;
            diskEl.className = 'status-value ' + getStatusClass(data.disk.percent);
            
            // Update status indicator
            const indicator = document.getElementById('system-status-indicator');
            indicator.className = 'status-indicator';
        } else {
            setSystemStatusError();
        }
    } catch (error) {
        console.error('Error fetching system status:', error);
        setSystemStatusError();
    }
}

function getStatusClass(percent) {
    if (percent >= 80) return 'critical';
    if (percent >= 60) return 'warning';
    return '';
}

function setSystemStatusError() {
    document.getElementById('host-cpu').textContent = 'Error';
    document.getElementById('host-ram').textContent = 'Error';
    document.getElementById('host-disk').textContent = 'Error';
    document.getElementById('system-status-indicator').className = 'status-indicator disconnected';
}



// ADDED BY DANK -----------------------------


// ---------------------- Right-click menu ----------------------

// Reference to container and menu
const container = document.getElementById('topology-network');
const menu = document.getElementById('node-context-menu');

// Disable default browser menu
container.addEventListener('contextmenu', e => e.preventDefault());

// Detect right-click on nodes
container.addEventListener('mousedown', e => {
    if (e.button !== 2) return; // Only right-click

    // Get node under mouse
    const nodeId = network.getNodeAt({ x: e.offsetX, y: e.offsetY });
    if (!nodeId) return; // Only show menu if clicked on a node

    // Get node data and check type
    const node = topologyData.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    // Only show menu for serf nodes (K3s clusters)
    const isK3sNode = node.type === 'k3s-node' || node.id.includes('serf');
    if (!isK3sNode) {
        return; // Don't show menu for routers/switches
    }


    menu.dataset.nodeId = nodeId;

    // Position menu near cursor with edge detection
    const menuWidth = 140;
    const menuHeight = 120;
    let left = e.pageX;
    let top = e.pageY;

    if (left + menuWidth > window.innerWidth) left = window.innerWidth - menuWidth - 10;
    if (top + menuHeight > window.innerHeight) top = window.innerHeight - menuHeight - 10;

    menu.style.left = left + 'px';
    menu.style.top = top + 'px';
    menu.style.display = 'block';
});

// Hide menu on click anywhere else
document.addEventListener('click', () => {
    menu.style.display = 'none';
});

// Menu item actions
//document.getElementById('menu-option-b').addEventListener('click', () => handleMenuAction('B'));
document.getElementById('menu-option-b').addEventListener('click', () => {
    const nodeId = menu.dataset.nodeId;
    menu.style.display = 'none';
    
    // Check if node has any Liqo connections
    const hasLiqoConnection = getDottedConnection(nodeId);
    
    if (!hasLiqoConnection) {
        alert('❌ No Liqo connection found!\n\nPlease create a Liqo connection first using "Liqo Connect".');
        return;
    }
    
    // Enter pod creation mode
    enterPodCreationMode(nodeId);
});



document.getElementById('menu-option-c').addEventListener('click', () => handleMenuAction('C'));

// Pod creation mode (similar to connect mode)
let podCreationMode = false;
let podCreationSourceNode = null;

function enterPodCreationMode(sourceNode) {
    podCreationMode = true;
    podCreationSourceNode = sourceNode;
    
    alert(`📦 Pod Creation Mode\n\nClick on the destination node (must have Liqo connection with ${sourceNode})`);
}

function handleMenuAction(option) {
    const nodeId = menu.dataset.nodeId;
    menu.style.display = 'none';

    if (option === 'B') {
        const edge = getDottedConnection(nodeId);

        if (!edge) {
            alert('No dotted connection found');
            return;
        }

        const from = edge.from === nodeId ? edge.from : edge.to;
        const to   = edge.from === nodeId ? edge.to   : edge.from;

        animatePodTransfer(from, to);
    }
    else if (option === 'C') {
        connectMode = true;
        connectFromNode = nodeId;
        alert(`Click another node to create a liqo connection from ${nodeId}`);
    } else {
        alert(`You clicked ${option} on node ${nodeId}`);
    }
}

/* function addVirtualClusterNode(nodeId) {
    const node = topologyData.nodes.find(n => n.id === nodeId);
    if (!node) return;

    const list = document.querySelector('.node-list'); // your existing UL

    if (!list) return;

    const li = document.createElement('li');
    li.textContent = `🔗 liqo-virtual-${node.label || node.id}`;

    list.appendChild(li);
} */

function getDottedConnection(nodeId) {
    const edges = network.body.data.edges.get();

    return edges.find(e =>
        e.dashes === true &&
        (e.from === nodeId || e.to === nodeId)
    );
}

function getLiqoPeers(nodeId) {
    const edges = network.body.data.edges.get();

    return [...new Set(
        edges
            .filter(e => e.dashes === true && (e.from === nodeId || e.to === nodeId))
            .map(e => e.from === nodeId ? e.to : e.from)
    )];
}


async function animatePodTransfer(fromId, toId) {
    if (!network) return;
 
    // Show popup with Liqo node
    showClusterPopupAboveNode(fromId, toId, true);
 
    const topRow = document.getElementById('cluster-top-row');
    const bottomRow = document.getElementById('cluster-bottom-row');
 
    // Animate pod loading in a DOM element
    async function hoverPodOverElement(elem, clusternodetext, iterations = 3, delay = 300) {
        for (let i = 0; i < iterations; i++) {
            elem.textContent = `${clusternodetext} (📦..)`;
            await new Promise(r => setTimeout(r, delay));
            elem.textContent = ` ${clusternodetext} (.📦.) `;
            await new Promise(r => setTimeout(r, delay));
            elem.textContent = `${clusternodetext} ( ..📦)   `;
            await new Promise(r => setTimeout(r, delay));
        }
        // Restore original
        elem.textContent = clusternodetext;
    }
 
    // Hover over master node in popup
    const masterElem = topRow.querySelector('.master');
    await hoverPodOverElement(masterElem, fromId);
 
    // Hover over Liqo node in popup
    const liqoElem = bottomRow.querySelector('.liqo');
    await hoverPodOverElement(liqoElem, "liqo-" + toId);
 
    // After hovering, run the old animation to target node
    const positions = network.getPositions([fromId, toId]);
    const start = positions[fromId];
    const end = positions[toId];
 
    const podId = 'pod-' + Date.now();
 
    // create temporary pod node
    network.body.data.nodes.add({
        id: podId,
        shape: 'text',
        label: '📦',
        font: { size: 20 },
        physics: false,
        x: start.x,
        y: start.y
    });
 
    const duration = 3000;
    const steps = 60;
    let step = 0;
 
    const interval = setInterval(() => {
        step++;
        const t = step / steps;
 
        const x = start.x + (end.x - start.x) * t;
        const y = start.y + (end.y - start.y) * t;
 
        network.body.data.nodes.update({
            id: podId,
            x,
            y
        });
 
        if (step >= steps) {
            clearInterval(interval);
 
            // remove pod
            network.body.data.nodes.remove(podId);
 
            // running effect on target
            flashNodeGreen(toId);
        }
    }, duration / steps);
}

function flashNodeGreen(nodeId) {
    let count = 0;

    const totalBlinks = 22;      // total toggles
    const successStart = 18;     // last 4 toggles = 2 green blinks

    const blink = setInterval(() => {
        let activeColor;

        if (count >= successStart) {
            // final phase → green
            activeColor = '#27ae60';
        } else {
            // deploying phase → orange
            activeColor = '#ae6f27ff';
        }

        const color = count % 2 === 0 ? activeColor : '#ffffff';

        network.body.data.nodes.update({
            id: nodeId,
            borderWidth: 6,
            color: {
                border: color,
                background: '#FFFFFF'
            }
        });

        count++;

        if (count > totalBlinks) {
            clearInterval(blink);

            // leave node solid green at end
            network.body.data.nodes.update({
                id: nodeId,
                borderWidth: 6,
                color: {
                    border: '#27ae60',
                    background: '#FFFFFF'
                }
            });
        }
    }, 150);
}


// ------------------ CLUSTER DISPLAY ------------------
function showClusterPopupAboveNode(fromId, toId, addLiqo = false) {
    const popup = document.getElementById('cluster-popup');
    const titleEl = document.getElementById('cluster-title'); 
    const topRow = document.getElementById('cluster-top-row');
    const bottomRow = document.getElementById('cluster-bottom-row');

    // Clear previous content
    topRow.innerHTML = '';
    bottomRow.innerHTML = '';

    // Update popup title dynamically
    titleEl.textContent = `K3s Cluster ${fromId}`;

    // Add Master Node to top row
    const masterDiv = document.createElement('div');
    masterDiv.className = 'cluster-node master';
    masterDiv.textContent = '' + fromId;
    topRow.appendChild(masterDiv);

    // Add Kwok Node to bottom row (hard-coded name for now)
    const kwokDiv = document.createElement('div');
    kwokDiv.className = 'cluster-node kwok';
    kwokDiv.textContent = 'kwok-emulation-node-1';
    bottomRow.appendChild(kwokDiv);

    const peers = getLiqoPeers(fromId);

    peers
    .filter(peerId => peerId !== toId)
    .forEach(peerId => {
        const peerDiv = document.createElement('div');
        peerDiv.className = 'cluster-node liqo-peer'; // IMPORTANT: different class
        peerDiv.textContent = 'liqo-' + peerId;
        bottomRow.appendChild(peerDiv);
    });

    // Add Liqo Virtual Node if needed
    if (addLiqo) {
        const liqoDiv = document.createElement('div');
        liqoDiv.className = 'cluster-node liqo';
        liqoDiv.textContent = 'liqo-' + toId;
        bottomRow.appendChild(liqoDiv);
    }

    // Get node position and convert to DOM coordinates
    const nodePosition = network.getPositions([fromId])[fromId];
    const canvasPosition = network.canvasToDOM({ x: nodePosition.x, y: nodePosition.y });

    // Dynamically adjust popup width based on content
    popup.style.width = 'auto';
    popup.style.display = 'block';
    const popupWidth = popup.offsetWidth;
    const popupHeight = popup.offsetHeight;

    // Position popup above the node
    popup.style.left = `${canvasPosition.x + popupWidth/3}px`;
    popup.style.top  = `${canvasPosition.y + popupHeight/3}px`;
}


// ------------------ LIQO LOCAL STORAGE ------------------

const LIQO_STORAGE_KEY = 'liqoConnections';

async function getSavedConnections() {
    try {
        const response = await fetch('/api/liqo-connections');
        const data = await response.json();
        return data.connections || [];
    } catch (error) {
        console.error('Error getting Liqo connections:', error);
        return [];
    }
}

async function saveLiqoConnection(from, to) {
    try {
        await fetch('/api/liqo-connections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from, to })
        });
    } catch (error) {
        console.error('Error saving Liqo connection:', error);
    }
}

async function removeLiqoConnectionFromServer(fromNode, toNode) {
    try {
        await fetch('/api/liqo-connections', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from: fromNode, to: toNode })
        });
    } catch (error) {
        console.error('Error removing Liqo connection:', error);
    }
}

function clearLiqoConnections() {
    localStorage.removeItem(LIQO_STORAGE_KEY);
}

async function restoreLiqoConnections() {
    const connections = await getSavedConnections();

    connections.forEach(conn => {
        network.body.data.edges.add({
            id: `restored-${conn.from}-${conn.to}`,
            from: conn.from,
            to: conn.to,
            dashes: true,
            width: 3,
            color: {
                color: '#27ae60',
                hover: '#27ae60',
                highlight: '#27ae60'
            }
        });
    });
}

async function getLiqoNodesForCluster(masterId) {
    const connections = await getSavedConnections();
    return connections
        .filter(c => c.from === masterId)
        .map(c => `🔗 liqo-${c.to}`);
}

document.getElementById('cluster-close')
    .addEventListener('click', () => {
        document.getElementById('cluster-popup').style.display = 'none';
    });

    


// // Virtual Pod Modal Functions
// async function openVirtualPodModal(sourceNode) {
//     const modal = document.getElementById('virtual-pod-modal');
    
//     // Set source node
//     document.getElementById('vp-source-node').value = sourceNode;
    
//     // Load available destination nodes (only serf nodes, excluding source)
//     const destSelect = document.getElementById('vp-dest-node');
//     destSelect.innerHTML = '<option value="">-- Select Destination --</option>';
    
//     topologyData.nodes
//         .filter(n => (n.type === 'k3s-node' || n.id.includes('serf')) && n.id !== sourceNode)
//         .forEach(node => {
//             const option = document.createElement('option');
//             option.value = node.id;
//             option.textContent = node.label || node.id;
//             destSelect.appendChild(option);
//         });
    
//     // Load workload templates
//     await loadWorkloadTemplates();
    
//     // Show modal
//     modal.style.display = 'block';
// }



async function loadWorkloadTemplates() {
    try {
        const response = await fetch('/api/workload-templates');
        const data = await response.json();
        
        const workloadSelect = document.getElementById('vp-workload');
        workloadSelect.innerHTML = '<option value="">-- Select Workload --</option>';
        
        data.templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template.filename;
            option.textContent = `${template.name} (${template.time_points} time points)`;
            option.dataset.timePoints = template.time_points;
            workloadSelect.appendChild(option);
        });
        
        // Add change listener for preview
        workloadSelect.addEventListener('change', function() {
            const selected = this.options[this.selectedIndex];
            if (selected.value) {
                showWorkloadPreview(selected.textContent);
            } else {
                document.getElementById('workload-preview').style.display = 'none';
            }
        });
        
    } catch (error) {
        console.error('Error loading workload templates:', error);
        alert('Failed to load workload templates');
    }
}

function showWorkloadPreview(info) {
    const preview = document.getElementById('workload-preview');
    const previewInfo = document.getElementById('preview-info');
    
    previewInfo.textContent = `This workload profile will be replayed on the destination node.`;
    preview.style.display = 'block';
}

function closeVirtualPodModal() {
    const modal = document.getElementById('virtual-pod-modal');
    modal.style.display = 'none';
    
    // Reset form
    document.getElementById('virtual-pod-form').reset();
    document.getElementById('workload-preview').style.display = 'none';
    document.getElementById('vp-creation-status').style.display = 'none';
}



// Open modal with pre-selected destination
async function openVirtualPodModalWithDestination(sourceNode, destNode) {
    const modal = document.getElementById('virtual-pod-modal');
    
    // Set source node
    document.getElementById('vp-source-node').value = sourceNode;
    
    // Load available destination nodes
    const destSelect = document.getElementById('vp-dest-node');
    destSelect.innerHTML = '<option value="">-- Select Destination --</option>';
    
    topologyData.nodes
        .filter(n => (n.type === 'k3s-node' || n.id.includes('serf')) && n.id !== sourceNode)
        .forEach(node => {
            const option = document.createElement('option');
            option.value = node.id;
            option.textContent = node.label || node.id;
            
            // Pre-select the clicked destination
            if (node.id === destNode) {
                option.selected = true;
            }
            
            destSelect.appendChild(option);
        });
    
    // Load workload templates
    await loadWorkloadTemplates();
    
    // Show modal
    modal.style.display = 'block';
}

// Update createVirtualPod function to trigger animation
async function createVirtualPod() {
    const sourceNode = document.getElementById('vp-source-node').value;
    const destNode = document.getElementById('vp-dest-node').value;
    const workloadFile = document.getElementById('vp-workload').value;
    const interval = parseInt(document.getElementById('vp-interval').value);
    
    if (!destNode || !workloadFile) {
        alert('Please select destination node and workload template');
        return;
    }
    
    // Show loading status
    const statusDiv = document.getElementById('vp-creation-status');
    const statusMsg = document.getElementById('vp-status-message');
    statusDiv.style.display = 'block';
    statusDiv.className = '';
    statusMsg.textContent = 'Creating virtual pod...';
    
    try {
        const response = await fetch('/api/virtual-pods/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source_node: sourceNode,
                dest_node: destNode,
                workload_file: workloadFile,
                interval: interval
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusDiv.className = 'success';
            statusMsg.textContent = '✓ Virtual pod created successfully!';
            
            // Close modal
            setTimeout(() => {
                closeVirtualPodModal();
            }, 1500);
            
            // START ANIMATION AFTER MODAL CLOSES
            setTimeout(() => {
                animatePodTransfer(sourceNode, destNode);
            }, 1600);
            
        } else {
            statusDiv.className = 'error';
            statusMsg.textContent = `✗ Error: ${result.error}`;
        }
        
    } catch (error) {
        statusDiv.className = 'error';
        statusMsg.textContent = `✗ Failed to create virtual pod: ${error.message}`;
    }
}

// Check if Liqo connection exists between two nodes
async function checkLiqoConnectionExists(fromNode, toNode) {
    const connections = await getSavedConnections();
    return connections.some(c =>
        (c.from === fromNode && c.to === toNode) ||
        (c.from === toNode && c.to === fromNode)
    );
}



// Load and display virtual pods
async function loadVirtualPods() {
    try {
        const response = await fetch('/api/virtual-pods');
        const data = await response.json();
        
        displayVirtualPods(data.virtual_pods || []);
        
    } catch (error) {
        console.error('Error loading virtual pods:', error);
    }
}

function displayVirtualPods(virtualPods) {
    const listDiv = document.getElementById('virtual-pods-list');
    
    if (!virtualPods || virtualPods.length === 0) {
        listDiv.innerHTML = '<p class="hint">No virtual pods created yet</p>';
        return;
    }
    
    let html = '';
    
    virtualPods.forEach(vp => {
        html += `
            <div class="virtual-pod-item ${vp.status === 'running' ? 'active' : ''}">
                <div class="virtual-pod-header">
                    <span class="virtual-pod-id">${vp.id}</span>
                    <span class="virtual-pod-status ${vp.status}">${vp.status}</span>
                </div>
                <div class="virtual-pod-route">
                    <span class="node-name">${vp.source_node}</span> 
                    → 
                    <span class="node-name">${vp.dest_node}</span>
                </div>
                <div style="font-size: 11px; color: #7F8C8D;">
                    📦 ${vp.source_pod_name}<br>
                    📦 ${vp.dest_pod_name}
                </div>
                <div class="virtual-pod-actions">
                    <button class="pod-action-btn pod-info-btn" onclick="showVirtualPodInfo('${vp.id}')">
                        ℹ️ Info
                    </button>
                    <button class="pod-action-btn pod-delete-btn" onclick="deleteVirtualPod('${vp.id}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    });
    
    listDiv.innerHTML = html;
}

// Show virtual pod info
function showVirtualPodInfo(podId) {
    fetch('/api/virtual-pods')
        .then(r => r.json())
        .then(data => {
            const vp = data.virtual_pods.find(p => p.id === podId);
            if (vp) {
                alert(`Virtual Pod: ${vp.id}\n\n` +
                      `Source: ${vp.source_node}/${vp.namespace}/${vp.source_pod_name}\n` +
                      `Destination: ${vp.dest_node}/${vp.namespace}/${vp.dest_pod_name}\n` +
                      `KWOK Node: ${vp.kwok_node}\n` +
                      `Workload: ${vp.workload_file}\n` +
                      `Interval: ${vp.interval}s\n` +
                      `Created: ${new Date(vp.created_at).toLocaleString()}\n` +
                      `Replayer PID: ${vp.replayer_pid}`);
            }
        });
}

// Delete virtual pod
async function deleteVirtualPod(podId) {
    if (!confirm(`Are you sure you want to delete virtual pod ${podId}?\n\nThis will:\n- Stop the replayer process\n- Delete pods from both nodes\n- Remove the virtual pod entry`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/virtual-pods/${podId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✓ Virtual pod ${podId} deleted successfully`);
            loadVirtualPods(); // Refresh list
        } else {
            alert(`✗ Error deleting virtual pod: ${result.error}`);
        }
        
    } catch (error) {
        alert(`✗ Failed to delete virtual pod: ${error.message}`);
    }
}


// // Ensure all modals are hidden on page load
// document.addEventListener('DOMContentLoaded', function() {
//     loadTopology();
//     startSystemStatusMonitoring();
//     loadVirtualPods();
    
//     // Hide all modals on load
//     document.getElementById('metrics-modal').style.display = 'none';
//     document.getElementById('virtual-pod-modal').style.display = 'none';
// });



// Add event listener for delete Liqo links
document.getElementById('menu-option-delete-liqo').addEventListener('click', async () => {
    const nodeId = menu.dataset.nodeId;
    menu.style.display = 'none';
    
    // Find all Liqo connections for this node
    const connections = await getSavedConnections();
    const nodeConnections = connections.filter(c => c.from === nodeId || c.to === nodeId);
    
    if (nodeConnections.length === 0) {
        alert(`No Liqo connections found for ${nodeId}`);
        return;
    }
    
    // Show selection dialog
    showDeleteLiqoLinksDialog(nodeId, nodeConnections);
});

// async function showDeleteLiqoLinksDialog(nodeId, connections) {
//     let message = `Select Liqo connections to remove from ${nodeId}:\n\n`;
    
//     connections.forEach((conn, index) => {
//         const otherNode = conn.from === nodeId ? conn.to : conn.from;
//         message += `${index + 1}. ${nodeId} ↔ ${otherNode}\n`;
//     });
    
//     message += `\nType numbers separated by commas (e.g., "1,2") or "all" to remove all:`;
    
//     const input = prompt(message);
    
//     if (!input) return; // Cancelled
    
//     if (input.toLowerCase() === 'all') {
//         // Remove all connections
//         connections.forEach(conn => {
//             await removeLiqoConnection(conn.from, conn.to);
//         });
//         alert(`✓ Removed ${connections.length} Liqo connection(s)`);
//     } else {
//         // Parse selection
//         const indices = input.split(',').map(s => parseInt(s.trim()) - 1);
//         let removed = 0;
        
//         indices.forEach(idx => {
//             if (idx >= 0 && idx < connections.length) {
//                 const conn = connections[idx];
//                 removeLiqoConnection(conn.from, conn.to);
//                 removed++;
//             }
//         });
        
//         alert(`✓ Removed ${removed} Liqo connection(s)`);
//     }
// }

async function removeLiqoConnection(fromNode, toNode) {
    // Remove from server
    await removeLiqoConnectionFromServer(fromNode, toNode);

    // Remove visual edge from network
    const edges = network.body.data.edges.get();
    const edgesToRemove = [];

    edges.forEach(edge => {
        if ((edge.from === fromNode && edge.to === toNode) ||
            (edge.from === toNode && edge.to === fromNode)) {
            if (edge.dashes === true) {
                edgesToRemove.push(edge.id);
            }
        }
    });

    if (edgesToRemove.length > 0) {
        network.body.data.edges.remove(edgesToRemove);
    }

    // Hide cluster popup if visible
    const popup = document.getElementById('cluster-popup');
    if (popup) popup.style.display = 'none';
}


let currentDeleteNode = null;
let currentDeleteConnections = [];

function showDeleteLiqoLinksDialog(nodeId, connections) {
    currentDeleteNode = nodeId;
    currentDeleteConnections = connections;
    
    const modal = document.getElementById('delete-liqo-modal');
    const nodeNameEl = document.getElementById('delete-liqo-node-name');
    const listEl = document.getElementById('liqo-connections-list');
    
    nodeNameEl.textContent = `Liqo connections for: ${nodeId}`;
    
    let html = '';
    connections.forEach((conn, index) => {
        const otherNode = conn.from === nodeId ? conn.to : conn.from;
        html += `
            <div class="liqo-connection-item">
                <input type="checkbox" id="liqo-conn-${index}" value="${index}">
                <label for="liqo-conn-${index}" class="liqo-connection-label">
                    ${nodeId} ↔ ${otherNode}
                </label>
            </div>
        `;
    });
    
    listEl.innerHTML = html;
    modal.style.display = 'block';
}

function closeDeleteLiqoModal() {
    document.getElementById('delete-liqo-modal').style.display = 'none';
    currentDeleteNode = null;
    currentDeleteConnections = [];
}

async function deleteSelectedLiqoLinks() {
    const checkboxes = document.querySelectorAll('#liqo-connections-list input[type="checkbox"]:checked');
    
    if (checkboxes.length === 0) {
        alert('Please select at least one connection to remove');
        return;
    }
    
    // Find all virtual pods that use these connections
    const affectedPods = [];
    
    try {
        const response = await fetch('/api/virtual-pods');
        const data = await response.json();
        const virtualPods = data.virtual_pods || [];
        
        checkboxes.forEach(cb => {
            const index = parseInt(cb.value);
            const conn = currentDeleteConnections[index];
            
            // Find pods that use this connection
            const podsOnConnection = virtualPods.filter(vp => 
                (vp.source_node === conn.from && vp.dest_node === conn.to) ||
                (vp.source_node === conn.to && vp.dest_node === conn.from)
            );
            
            affectedPods.push(...podsOnConnection);
        });
        
        // Show confirmation with affected pods
        if (affectedPods.length > 0) {
            let confirmMsg = `⚠️ WARNING: Removing these Liqo connections will also delete ${affectedPods.length} virtual pod(s):\n\n`;
            affectedPods.forEach(vp => {
                confirmMsg += `  • ${vp.id}: ${vp.source_node} → ${vp.dest_node}\n`;
            });
            confirmMsg += `\nContinue?`;
            
            if (!confirm(confirmMsg)) {
                return;
            }
        }
        
        // Delete virtual pods first
        let deletedPods = 0;
        for (const vp of affectedPods) {
            try {
                const deleteResponse = await fetch(`/api/virtual-pods/${vp.id}`, {
                    method: 'DELETE'
                });
                if (deleteResponse.ok) {
                    deletedPods++;
                }
            } catch (error) {
                console.error(`Failed to delete virtual pod ${vp.id}:`, error);
            }
        }
        
        // Then remove Liqo connections
        let removedConnections = 0;
        for (const cb of checkboxes) {
            const index = parseInt(cb.value);
            const conn = currentDeleteConnections[index];
            await removeLiqoConnection(conn.from, conn.to);
            removedConnections++;
        }
        
        // Show success message
        let successMsg = `✓ Removed ${removedConnections} Liqo connection(s)`;
        if (deletedPods > 0) {
            successMsg += `\n✓ Deleted ${deletedPods} virtual pod(s)`;
        }
        alert(successMsg);
        
        // Refresh virtual pods list
        loadVirtualPods();
        
        closeDeleteLiqoModal();
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}





//-----------------------------------------------------------------
//---------ADD functions above these lines-------------------------

document.addEventListener('DOMContentLoaded', function() {
    // Initialize topology and monitoring
    loadTopology();
    startSystemStatusMonitoring();
    loadVirtualPods();
    
    // Clear old localStorage data
    localStorage.removeItem('liqoConnections');
    
    // Hide all modals on load
    document.getElementById('metrics-modal').style.display = 'none';
    document.getElementById('virtual-pod-modal').style.display = 'none';
    document.getElementById('delete-liqo-modal').style.display = 'none';

    // Close metrics modal X button
    const closeBtn = document.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeMetricsModal);
    }
    
    // Close metrics modal when clicking outside
    window.addEventListener('click', function(event) {
        const modal = document.getElementById('metrics-modal');
        if (event.target === modal) {
            closeMetricsModal();
        }
    });
    
    // Handle virtual pod form submission
    const form = document.getElementById('virtual-pod-form');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            await createVirtualPod();
        });
    }
});