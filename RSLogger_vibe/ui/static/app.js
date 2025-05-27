class WebSocketControlCenter {
    constructor() {
        this.ws = null;
        this.recorders = {};
        this.recordings = [];
        
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            recordersGrid: document.getElementById('recordersGrid'),
            recordingsList: document.getElementById('recordingsList'),
            refreshRecorders: document.getElementById('refreshRecorders'),
            startAllButton: document.getElementById('startAllButton'),
            stopAllButton: document.getElementById('stopAllButton'),
            masterDuration: document.getElementById('masterDuration'),
            notification: document.getElementById('notification')
        };
        
        this.initializeEventListeners();
        this.connectWebSocket();
    }
    
    initializeEventListeners() {
        this.elements.refreshRecorders.addEventListener('click', () => this.refreshRecorders());
        this.elements.startAllButton.addEventListener('click', () => this.startAllRecording());
        this.elements.stopAllButton.addEventListener('click', () => this.stopAllRecording());
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.updateConnectionStatus(true);
            this.refreshRecorders();
        };
        
        this.ws.onclose = () => {
            this.updateConnectionStatus(false);
            // Attempt to reconnect after 2 seconds
            setTimeout(() => this.connectWebSocket(), 2000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showNotification('Connection error', 'error');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
    }
    
    handleWebSocketMessage(data) {
        console.log('Received:', data);
        
        switch (data.type) {
            case 'initial_state':
                this.recorders = data.recorders || {};
                this.recordings = data.recordings || [];
                this.updateUI();
                break;
                
            case 'recorder_status':
                this.recorders[data.client_id] = data.status;
                this.updateRecorderCard(data.client_id);
                break;
                
            case 'recorder_connected':
                this.showNotification(`Recorder ${data.client_id} connected`, 'info');
                this.refreshRecorders();
                break;
                
            case 'recorder_disconnected':
                delete this.recorders[data.client_id];
                this.updateRecordersGrid();
                this.showNotification(`Recorder ${data.client_id} disconnected`, 'warning');
                break;
                
            case 'recorder_recording_started':
                if (this.recorders[data.data.client_id]) {
                    this.recorders[data.data.client_id].recording = true;
                    this.updateRecorderCard(data.data.client_id);
                }
                this.showNotification(`Recording started on ${data.data.client_id}`, 'success');
                break;
                
            case 'recorder_recording_completed':
                if (this.recorders[data.data.client_id]) {
                    this.recorders[data.data.client_id].recording = false;
                    this.updateRecorderCard(data.data.client_id);
                }
                this.showNotification(`Recording completed on ${data.data.client_id}`, 'success');
                this.refreshRecordings();
                break;
                
            case 'recorder_recording_error':
                if (this.recorders[data.data.client_id]) {
                    this.recorders[data.data.client_id].recording = false;
                    this.updateRecorderCard(data.data.client_id);
                }
                this.showNotification(`Error on ${data.data.client_id}: ${data.data.error}`, 'error');
                break;
                
            case 'recorder_error':
                this.showNotification(`Error from ${data.client_id}: ${data.error}`, 'error');
                break;
                
            case 'recordings_updated':
                this.recordings = data.recordings;
                this.updateRecordingsList();
                break;
                
            case 'command_response':
                console.log(`Response from ${data.client_id}:`, data.response);
                break;
        }
    }
    
    updateConnectionStatus(connected) {
        const statusEl = this.elements.connectionStatus;
        if (connected) {
            statusEl.classList.add('connected');
            statusEl.querySelector('.status-text').textContent = 'Connected';
        } else {
            statusEl.classList.remove('connected');
            statusEl.querySelector('.status-text').textContent = 'Disconnected';
        }
    }
    
    updateUI() {
        this.updateRecordersGrid();
        this.updateRecordingsList();
    }
    
    updateRecordersGrid() {
        const grid = this.elements.recordersGrid;
        const recorderIds = Object.keys(this.recorders);
        
        if (recorderIds.length === 0) {
            grid.innerHTML = '<p class="no-recorders">No recorders connected</p>';
            return;
        }
        
        grid.innerHTML = recorderIds.map(id => this.createRecorderCard(id)).join('');
        
        // Add event listeners to recorder buttons
        recorderIds.forEach(id => {
            const startBtn = document.getElementById(`start-${id}`);
            const stopBtn = document.getElementById(`stop-${id}`);
            const applyBtn = document.getElementById(`apply-${id}`);
            
            if (startBtn) {
                startBtn.addEventListener('click', () => this.startRecording(id));
            }
            if (stopBtn) {
                stopBtn.addEventListener('click', () => this.stopRecording(id));
            }
            if (applyBtn) {
                applyBtn.addEventListener('click', () => this.applyConfig(id));
            }
        });
    }
    
    updateRecorderCard(clientId) {
        const existingCard = document.getElementById(`recorder-${clientId}`);
        if (existingCard) {
            const newCard = this.createRecorderCard(clientId);
            const temp = document.createElement('div');
            temp.innerHTML = newCard;
            existingCard.replaceWith(temp.firstElementChild);
            
            // Re-add event listeners
            const startBtn = document.getElementById(`start-${clientId}`);
            const stopBtn = document.getElementById(`stop-${clientId}`);
            const applyBtn = document.getElementById(`apply-${clientId}`);
            
            if (startBtn) {
                startBtn.addEventListener('click', () => this.startRecording(clientId));
            }
            if (stopBtn) {
                stopBtn.addEventListener('click', () => this.stopRecording(clientId));
            }
            if (applyBtn) {
                applyBtn.addEventListener('click', () => this.applyConfig(clientId));
            }
        } else {
            this.updateRecordersGrid();
        }
    }
    
    createRecorderCard(id) {
        const recorder = this.recorders[id];
        const isRecording = recorder.recording || false;
        const config = recorder.config || {};
        const capabilities = recorder.capabilities || {};
        
        return `
            <div class="recorder-card ${isRecording ? 'recording' : ''}" id="recorder-${id}">
                <div class="recorder-header">
                    <div class="recorder-name">${id}</div>
                    <div class="recorder-status ${isRecording ? 'recording' : ''}">
                        <span class="status-indicator"></span>
                        ${isRecording ? 'Recording' : 'Ready'}
                    </div>
                </div>
                <div class="recorder-details">
                    <div class="config-row">
                        <label>Device:</label>
                        <select class="recorder-config" id="device-${id}" ${isRecording ? 'disabled' : ''}>
                            ${capabilities.devices ? capabilities.devices.map(dev => 
                                `<option value="${dev.id}" ${dev.is_current ? 'selected' : ''}>${dev.name}</option>`
                            ).join('') : `<option value="${config.device}">${config.device_name || 'Default'}</option>`}
                        </select>
                    </div>
                    <div class="config-row">
                        <label>Sample Rate:</label>
                        <select class="recorder-config" id="samplerate-${id}" ${isRecording ? 'disabled' : ''}>
                            ${capabilities.supported_samplerates ? capabilities.supported_samplerates.map(rate => 
                                `<option value="${rate}" ${rate === config.samplerate ? 'selected' : ''}>${rate} Hz</option>`
                            ).join('') : `<option value="${config.samplerate}">${config.samplerate} Hz</option>`}
                        </select>
                    </div>
                    <div class="config-row">
                        <label>Channels:</label>
                        <select class="recorder-config" id="channels-${id}" ${isRecording ? 'disabled' : ''}>
                            ${capabilities.supported_channels ? capabilities.supported_channels.map(ch => 
                                `<option value="${ch}" ${ch === config.channels ? 'selected' : ''}>${ch === 1 ? 'Mono' : 'Stereo'}</option>`
                            ).join('') : `<option value="${config.channels}">${config.channels}ch</option>`}
                        </select>
                    </div>
                </div>
                <div class="recorder-controls">
                    <button class="recorder-button" id="start-${id}" ${isRecording ? 'disabled' : ''}>
                        <span class="material-icons">play_arrow</span>
                        Start
                    </button>
                    <button class="recorder-button stop" id="stop-${id}" ${!isRecording ? 'disabled' : ''}>
                        <span class="material-icons">stop</span>
                        Stop
                    </button>
                    <button class="recorder-button config" id="apply-${id}" ${isRecording ? 'disabled' : ''} title="Apply Configuration">
                        <span class="material-icons">save</span>
                    </button>
                </div>
            </div>
        `;
    }
    
    updateRecordingsList() {
        const listEl = this.elements.recordingsList;
        
        if (this.recordings.length === 0) {
            listEl.innerHTML = '<p class="no-recordings">No recordings yet</p>';
            return;
        }
        
        listEl.innerHTML = this.recordings.map(recording => `
            <div class="recording-item">
                <div class="recording-info">
                    <div class="recording-name">${recording.filename}</div>
                    <div class="recording-details">
                        ${this.formatDate(recording.created)} • 
                        ${this.formatFileSize(recording.size)} • 
                        ${recording.metadata.duration ? `${recording.metadata.duration.toFixed(1)}s` : 'Unknown duration'} • 
                        ${recording.metadata.client_id || 'Unknown recorder'}
                    </div>
                </div>
                <div class="recording-actions">
                    <button class="icon-button" onclick="app.downloadRecording('${recording.filename}')" title="Download">
                        <span class="material-icons">download</span>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    refreshRecorders() {
        this.sendCommand('all', 'get_status');
        this.refreshRecordings();
    }
    
    refreshRecordings() {
        this.ws.send(JSON.stringify({
            type: 'get_recordings'
        }));
    }
    
    startRecording(clientId) {
        const duration = this.elements.masterDuration.value ? 
            parseFloat(this.elements.masterDuration.value) : null;
            
        this.sendCommand(clientId, 'start_recording', { duration });
    }
    
    stopRecording(clientId) {
        this.sendCommand(clientId, 'stop_recording');
    }
    
    startAllRecording() {
        const duration = this.elements.masterDuration.value ? 
            parseFloat(this.elements.masterDuration.value) : null;
            
        this.sendCommand('all', 'start_recording', { duration });
    }
    
    stopAllRecording() {
        this.sendCommand('all', 'stop_recording');
    }
    
    sendCommand(clientId, command, payload = {}) {
        this.ws.send(JSON.stringify({
            type: 'command',
            client_id: clientId,
            command: command,
            payload: payload
        }));
    }
    
    applyConfig(clientId) {
        const deviceSelect = document.getElementById(`device-${clientId}`);
        const samplerateSelect = document.getElementById(`samplerate-${clientId}`);
        const channelsSelect = document.getElementById(`channels-${clientId}`);
        
        if (!deviceSelect || !samplerateSelect || !channelsSelect) {
            return;
        }
        
        const newConfig = {
            device: parseInt(deviceSelect.value),
            samplerate: parseInt(samplerateSelect.value),
            channels: parseInt(channelsSelect.value)
        };
        
        this.sendCommand(clientId, 'update_config', newConfig);
        this.showNotification(`Configuration updated for ${clientId}`, 'success');
    }
    
    downloadRecording(filename) {
        window.open(`/api/recordings/${filename}`, '_blank');
    }
    
    showNotification(message, type = 'info') {
        const notif = this.elements.notification;
        const textEl = notif.querySelector('.notification-text');
        
        textEl.textContent = message;
        notif.className = 'notification show ' + type;
        
        setTimeout(() => {
            notif.classList.remove('show');
        }, 3000);
    }
    
    formatDate(isoDate) {
        const date = new Date(isoDate);
        return date.toLocaleString();
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Initialize app when DOM is loaded
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new WebSocketControlCenter();
});