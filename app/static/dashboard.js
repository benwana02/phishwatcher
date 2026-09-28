// Dashboard JavaScript

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadProfiles();
    loadNetworkVisualization();
});

// Load system statistics
async function loadStats() {
    try {
        const response = await axios.get('/stats');
        const stats = response.data.stats;
        
        const statsGrid = document.getElementById('stats-grid');
        statsGrid.innerHTML = `
            <div class="stat-item">
                <div class="stat-value">${stats.profiles_count}</div>
                <div class="stat-label">Sender Profiles</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${stats.network_nodes}</div>
                <div class="stat-label">Network Nodes</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${stats.network_edges}</div>
                <div class="stat-label">Network Edges</div>
            </div>
        `;
    } catch (error) {
        document.getElementById('stats-grid').innerHTML = 
            `<div class="error">Error loading statistics: ${error.message}</div>`;
    }
}

// Load sender profiles list
const profilesPageSize = 10;

async function loadProfiles(offset = 0) {
    try {
        const response = await axios.get('/profiles', {
            params: { limit: profilesPageSize, offset: offset }
        });
        const profiles = response.data.profiles;
        const totalCount = response.data.count;

        const profilesList = document.getElementById('profiles-list');

        if (totalCount === 0) {
            profilesList.innerHTML = '<div class="error">No profiles found. Please run the profile builder first.</div>';
            return;
        }

        let html = '<div class="profiles-table">';
        html += '<table style="width: 100%; border-collapse: collapse;">';
        html += '<tr><th>Sender</th><th>Emails</th><th>Recipients</th><th>Last Seen</th><th>Actions</th></tr>';

        profiles.forEach(profile => {
            html += `
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px;">${profile.sender}</td>
                    <td style="padding: 10px; text-align: center;">${profile.total_emails}</td>
                    <td style="padding: 10px; text-align: center;">${profile.unique_recipients}</td>
                    <td style="padding: 10px;">${profile.last_seen ? profile.last_seen.split('T')[0] : 'N/A'}</td>
                    <td style="padding: 10px;">
                        <button class="btn" onclick="viewProfile('${profile.sender}')" style="padding: 5px 10px; font-size: 0.9rem;">View</button>
                        <button class="btn-secondary" onclick="useAsSender('${profile.sender}')" style="padding: 5px 10px; font-size: 0.9rem;">Use</button>
                    </td>
                </tr>
            `;
        });
        html += '</table>';

        const start = offset + 1;
        const end = Math.min(offset + profilesPageSize, totalCount);
        html += `<div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">`;
        html += `<p style="color: #666; margin: 0;">Showing ${start}-${end} of ${totalCount} profiles</p>`;
        html += `<div>`;
        html += `<button class="btn-secondary" onclick="loadProfiles(${Math.max(0, offset - profilesPageSize)})" ${offset === 0 ? 'disabled' : ''} style="padding: 5px 10px; font-size: 0.9rem; margin-right: 5px;">Previous</button>`;
        html += `<button class="btn-secondary" onclick="loadProfiles(${offset + profilesPageSize})" ${end >= totalCount ? 'disabled' : ''} style="padding: 5px 10px; font-size: 0.9rem;">Next</button>`;
        html += `</div></div></div>`;

        profilesList.innerHTML = html;
    } catch (error) {
        document.getElementById('profiles-list').innerHTML =
            `<div class="error">Error loading profiles: ${error.message}</div>`;
    }
}

// Load network visualization
async function loadNetworkVisualization() {
    try {
        const response = await axios.get('/network/visualization');
        const networkViz = document.getElementById('network-viz');
        
        if (response.data.image_url) {
            networkViz.innerHTML = `
                <img src="${response.data.image_url}" alt="Network Visualization" 
                     style="width: 100%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <p style="margin-top: 10px; text-align: center; color: #666;">
                    Communication network visualization
                </p>
            `;
        }
    } catch (error) {
        document.getElementById('network-viz').innerHTML = 
            `<div class="error">Error loading network visualization: ${error.message}</div>`;
    }
}

// View detailed profile
async function viewProfile(sender) {
    try {
        const response = await axios.get(`/profile/${encodeURIComponent(sender)}`);
        const profile = response.data.profile;

        // Top 5 most-emailed recipients, for a quick sanity check
        const topRecipients = Object.entries(profile.recipient_frequencies || {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([addr, count]) => `  ${addr}: ${count}`)
            .join('\n');

        const lang = profile.language_profile || {};

        alert(`Profile for ${sender}:\n\n` +
              `Total Emails: ${profile.total_emails}\n` +
              `Unique Recipients: ${profile.unique_recipients_count}\n` +
              `First Seen: ${profile.first_seen}\n` +
              `Last Seen: ${profile.last_seen}\n` +
              `Average Subject Length: ${profile.avg_subject_length.toFixed(1)} chars\n` +
              `Average Body Length: ${profile.avg_body_length.toFixed(1)} chars\n\n` +
              `Top 5 Recipients:\n${topRecipients}\n\n` +
              `Language Baseline:\n` +
              `  Urgency Score: ${(lang.urgency_score || 0).toFixed(3)}\n` +
              `  Formality Score: ${(lang.formality_score || 0).toFixed(3)}\n` +
              `  Exclamation Density: ${(lang.exclamation_density || 0).toFixed(3)}\n` +
              `  Avg Sentence Length: ${(lang.avg_sentence_length || 0).toFixed(1)}`);

        // Everything else (full recipient list, hourly/daily distribution,
        // stylometric writeprint vectors) is available here for inspection
        // without further code changes:
        console.log('Full profile:', profile);
    } catch (error) {
        alert(`Error loading profile: ${error.message}`);
    }
}

// Use profile sender in form
function useAsSender(sender) {
    document.getElementById('sender').value = sender;
}

// Generate test email
async function generateTest(pattern) {
    try {
        const response = await axios.post('/generate-test', { pattern: pattern });
        const email = response.data.email;
        
        document.getElementById('sender').value = email.sender;
        document.getElementById('recipients').value = email.recipients.join(', ');
        document.getElementById('subject').value = email.subject;
        document.getElementById('body').value = email.body;
        
        // Auto-analyze
        analyzeEmail(new Event('submit'));
    } catch (error) {
        alert(`Error generating test email: ${error.message}`);
    }
}

// Analyze sample email
function analyzeSample() {
    document.getElementById('sender').value = 'john.doe@enron.com';
    document.getElementById('recipients').value = 'unusual.recipient@external.com, colleague@enron.com';
    document.getElementById('subject').value = 'URGENT: Verify Your Account Immediately';
    document.getElementById('body').value = 'Dear User,\n\nWe have detected unusual activity on your account. Please verify your credentials immediately by clicking the link below:\n\nhttp://fake-verify.com/login\n\nFailure to verify within 24 hours will result in account suspension.\n\nBest regards,\nSecurity Team';
    
    analyzeEmail(new Event('submit'));
}

// Analyze email form submission
async function analyzeEmail(event) {
    event.preventDefault();
    
    const emailData = {
        sender: document.getElementById('sender').value,
        recipients: document.getElementById('recipients').value.split(',').map(r => r.trim()),
        subject: document.getElementById('subject').value,
        body: document.getElementById('body').value,
        timestamp: new Date().toISOString()
    };
    
    try {
        const response = await axios.post('/analyze', emailData);
        displayResults(response.data.analysis, response.data.sender_profile);
        
        // Scroll to results
        document.getElementById('results-card').scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        alert(`Error analyzing email: ${error.message}`);
    }
}

// Display analysis results
function displayResults(analysis, profile) {
    // Show results card
    document.getElementById('results-card').style.display = 'block';
    
    // Update score
    const score = analysis.composite_score;
    document.getElementById('score-value').textContent = score.toFixed(3);
    document.getElementById('score-fill').style.width = `${score * 100}%`;
    
    // Update risk badge
    const riskLevel = analysis.risk_level;
    const riskBadgeContainer = document.getElementById('risk-badge-container');
    riskBadgeContainer.innerHTML = `
        <span class="risk-badge risk-${riskLevel.toLowerCase()}">
            ${riskLevel} RISK
        </span>
        <p>Anomaly detected: ${score >= 0.4 ? 'Yes' : 'No'}</p>
    `;
    
    // Create chart
    createAnomalyChart(analysis);
    
    // Display reasons
    const reasonsContainer = document.getElementById('reasons-container');
    if (analysis.reasons && analysis.reasons.length > 0) {
        let reasonsHtml = '<div class="reasons-list">';
        analysis.reasons.forEach(reason => {
            reasonsHtml += `<div class="reason-item">• ${reason}</div>`;
        });
        reasonsHtml += '</div>';
        reasonsContainer.innerHTML = reasonsHtml;
    } else {
        reasonsContainer.innerHTML = '<p>No specific anomalies detected.</p>';
    }
    
    // Display profile info
    const profileInfo = document.getElementById('profile-info');
    if (profile) {
        profileInfo.innerHTML = `
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value">${profile.total_emails}</div>
                    <div class="stat-label">Total Emails</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${profile.unique_recipients_count}</div>
                    <div class="stat-label">Unique Recipients</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${profile.avg_subject_length.toFixed(0)}</div>
                    <div class="stat-label">Avg Subject Length</div>
                </div>
            </div>
            <p style="margin-top: 10px;">
                <strong>First Seen:</strong> ${profile.first_seen ? profile.first_seen.split('T')[0] : 'Unknown'}<br>
                <strong>Last Seen:</strong> ${profile.last_seen ? profile.last_seen.split('T')[0] : 'Unknown'}
            </p>
        `;
    } else {
        profileInfo.innerHTML = '<div class="error">No profile found for this sender</div>';
    }
}

// Create anomaly breakdown chart
function createAnomalyChart(analysis) {
    const ctx = document.getElementById('anomaly-chart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (window.anomalyChart) {
        window.anomalyChart.destroy();
    }
    
    const data = {
        labels: ['Recipient', 'Temporal', 'Content', 'Behavioral', 'Composite'],
        datasets: [{
            label: 'Anomaly Score',
            data: [
                analysis.recipient_anomaly,
                analysis.temporal_anomaly,
                analysis.content_anomaly,
                analysis.behavioral_anomaly,
                analysis.composite_score
            ],
            backgroundColor: [
                'rgba(255, 99, 132, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 206, 86, 0.6)',
                'rgba(75, 192, 192, 0.6)',
                'rgba(153, 102, 255, 0.6)'
            ],
            borderColor: [
                'rgba(255, 99, 132, 1)',
                'rgba(54, 162, 235, 1)',
                'rgba(255, 206, 86, 1)',
                'rgba(75, 192, 192, 1)',
                'rgba(153, 102, 255, 1)'
            ],
            borderWidth: 1
        }]
    };
    
    const config = {
        type: 'bar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0,
                    title: {
                        display: true,
                        text: 'Anomaly Score'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y.toFixed(3)}`;
                        }
                    }
                }
            }
        }
    };
    
    window.anomalyChart = new Chart(ctx, config);
}