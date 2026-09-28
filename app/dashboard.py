"""
Flask Dashboard for PhishWatcher
"""
import matplotlib
matplotlib.use('Agg')   # MUST be the very first matplotlib-related line in the whole app

from flask import Flask, render_template, request, jsonify, send_file
import sys
import os
import json
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.behavioral_analysis.profile_builder import ProfileBuilder, SenderProfile
from src.behavioral_analysis.anomaly_detector import AnomalyDetector
from src.behavioral_analysis.network_analyzer import CommunicationNetwork
from src.utils.email_simulator import EmailSimulator
from src.behavioral_analysis.stylometric_detector import StylometricAnomalyDetector   
from src.behavioral_analysis.ensemble_detector import EnsembleDetector
from src.utils.impersonation_simulator import ImpersonationSimulator                 

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Global variables (in production, use a proper database)
PROFILES = {}
DETECTOR = None
NETWORK = None
SIMULATOR = None
IMPERSONATION_SIMULATOR = None

def init_system():
    """Initialize the system components"""
    global PROFILES, DETECTOR, NETWORK, SIMULATOR, IMPERSONATION_SIMULATOR
    
    # Paths
    db_path = "data/emails.db"
    profiles_path = "data/profiles/profiles.json"
    network_path = "data/network/communication_network.json"
    
    try:
        # Load profiles
        if os.path.exists(profiles_path):
            builder = ProfileBuilder(db_path)
            builder.load_profiles(profiles_path)
            PROFILES = builder.profiles
            print(f"Loaded {len(PROFILES)} profiles")
        else:
            print("No profiles found")
            PROFILES = {}
        
        # Load network
        if os.path.exists(network_path):
            NETWORK = CommunicationNetwork()
            NETWORK.load_network(network_path)
            print(f"Loaded network with {NETWORK.graph.number_of_nodes()} nodes")
        
        # Create detector
        # Create the two uni-modal detectors named in the proposal, then fuse them
        behavioral_detector = AnomalyDetector(PROFILES, NETWORK)
        stylometric_detector = StylometricAnomalyDetector(PROFILES)
        DETECTOR = EnsembleDetector(
            [behavioral_detector, stylometric_detector],
            weights=[0.5, 0.5],
        )
        
        # Create simulator
        SIMULATOR = EmailSimulator(profiles_path)
        IMPERSONATION_SIMULATOR = ImpersonationSimulator(db_path)
        
        print("System initialized successfully")
        
    except Exception as e:
        print(f"Error initializing system: {e}")

# Initialize on startup
init_system()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_email():
    """Analyze a single email"""
    try:
        data = request.json

        if not data or 'sender' not in data:
            return jsonify({'error': 'Missing email data'}), 400

        # Convert timestamp string to datetime
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        # Analyze email
        if DETECTOR:
            score = DETECTOR.analyze_email(data)

            # DETECTOR is an EnsembleDetector, which returns
            # {'ensemble_composite': ..., 'ensemble_components': {...}, 'reasons': [...]}
            # -- reshape this into the flat shape dashboard.js expects
            # (composite_score, risk_level, and each component as a top-level
            # key), matching what AnomalyScore.to_dict() used to return.
            components = score.get('ensemble_components', {})
            composite = score.get('ensemble_composite', 0.0)

            def get_risk_level(s):
                if s >= 0.8:
                    return "CRITICAL"
                elif s >= 0.6:
                    return "HIGH"
                elif s >= 0.4:
                    return "MEDIUM"
                elif s >= 0.2:
                    return "LOW"
                else:
                    return "NORMAL"

            analysis = {
                'recipient_anomaly': components.get('recipient_anomaly', 0.0),
                'temporal_anomaly': components.get('temporal_anomaly', 0.0),
                'content_anomaly': components.get('content_anomaly', 0.0),
                'behavioral_anomaly': components.get('behavioral_anomaly', 0.0),
                'stylometric_anomaly': components.get('stylometric_anomaly', 0.0),
                'composite_score': composite,
                'risk_level': get_risk_level(composite),
                'reasons': score.get('reasons', []),
            }

            # Get sender profile if exists
            sender_profile = None
            if data['sender'] in PROFILES:
                sender_profile = PROFILES[data['sender']].to_dict()

            return jsonify({
                'success': True,
                'analysis': analysis,
                'sender_profile': sender_profile
            })
        else:
            return jsonify({'error': 'System not initialized'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profiles')
def list_profiles():
    """List all sender profiles"""
    try:
        limit = request.args.get('limit', default=10, type=int)
        offset = request.args.get('offset', default=0, type=int)
        search = request.args.get('search', default='', type=str).lower()

        profiles_list = []
        for sender, profile in PROFILES.items():
            if search and search not in sender.lower():
                continue
            profiles_list.append({
                'sender': sender,
                'total_emails': profile.total_emails,
                'unique_recipients': len(profile.unique_recipients),
                'first_seen': profile.first_seen.isoformat() if profile.first_seen else None,
                'last_seen': profile.last_seen.isoformat() if profile.last_seen else None,
            })

        profiles_list.sort(key=lambda x: x['total_emails'], reverse=True)
        total_count = len(profiles_list)

        return jsonify({
            'success': True,
            'count': total_count,
            'offset': offset,
            'limit': limit,
            'profiles': profiles_list[offset:offset + limit]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile/<sender>')
def get_profile(sender):
    """Get detailed profile for a sender"""
    try:
        if sender not in PROFILES:
            return jsonify({'error': 'Profile not found'}), 404
        
        profile = PROFILES[sender].to_dict()
        
        # Add network analysis if available
        if NETWORK and sender in NETWORK.graph:
            network_analysis = NETWORK.analyze_sender_network(sender)
            profile['network_analysis'] = network_analysis
        
        return jsonify({
            'success': True,
            'profile': profile
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-test', methods=['POST'])
def generate_test_email():
    """Generate a test email"""
    try:
        data = request.json
        pattern = data.get('pattern', 'normal')
        sender = data.get('sender')

        if not sender and PROFILES:
            import random
            sender = random.choice(list(PROFILES.keys()))

        if not sender:
            return jsonify({'error': 'No sender specified and no profiles available'}), 400

        # 'normal' now draws a REAL historical email for this sender instead
        # of synthesizing placeholder "xxxxx" filler text, which was never
        # a realistic test of "does this look like normal behaviour".
        if pattern == 'normal':
            email = IMPERSONATION_SIMULATOR.generate_normal(sender)
            if email is None:
                return jsonify({'error': f'No historical emails found for {sender}'}), 404
            email['timestamp'] = email['timestamp'].isoformat()
        else:
            email = SIMULATOR.generate_email(sender, pattern)
            email['timestamp'] = email['timestamp'].isoformat()

        return jsonify({
            'success': True,
            'email': email
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/network/visualization')
def get_network_visualization():
    """Get network visualization"""
    try:
        if not NETWORK:
            return jsonify({'error': 'Network not available'}), 404

        # Generate visualization — anchor to Flask's actual static folder,
        # not the current working directory, so the saved file and the
        # URL Flask serves it from always agree.
        viz_path = os.path.join(app.static_folder, "network.png")
        os.makedirs(os.path.dirname(viz_path), exist_ok=True)

        # Get top senders for highlighting
        top_senders = sorted(
            [(node, data['email_count']) for node, data in NETWORK.nodes.items()
             if data.get('type') == 'sender'],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        highlight_nodes = [sender for sender, _ in top_senders]
        NETWORK.visualize_network(viz_path, highlight_nodes)

        return jsonify({
            'success': True,
            'image_url': '/static/network.png'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stats')
def get_stats():
    """Get system statistics"""
    try:
        stats = {
            'profiles_count': len(PROFILES),
            'network_nodes': NETWORK.graph.number_of_nodes() if NETWORK else 0,
            'network_edges': NETWORK.graph.number_of_edges() if NETWORK else 0,
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Run the app
    app.run(debug=True, port=5000, threaded=True)