"""
Network Analyzer - Analyzes communication networks and relationships
"""

import networkx as nx
import matplotlib
matplotlib.use('Agg')   # non-interactive backend, safe for web servers
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Set
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class CommunicationNetwork:
    """Represents email communication network"""
    
    def __init__(self):
        self.graph = nx.DiGraph()  # Directed graph
        self.nodes = {}  # Node attributes
        self.edges = {}  # Edge attributes
        
    def add_email(self, sender: str, recipients: List[str], timestamp: datetime):
        """Add an email to the network"""
        # Add sender node
        if sender not in self.graph:
            self.graph.add_node(sender)
            self.nodes[sender] = {'type': 'sender', 'email_count': 0}
        
        self.nodes[sender]['email_count'] += 1
        
        # Add recipients and edges
        for recipient in recipients:
            if recipient not in self.graph:
                self.graph.add_node(recipient)
                self.nodes[recipient] = {'type': 'recipient', 'email_count': 0}
            
            self.nodes[recipient]['email_count'] += 1
            
            # Add or update edge
            edge_key = (sender, recipient)
            if edge_key in self.edges:
                self.edges[edge_key]['weight'] += 1
                self.edges[edge_key]['timestamps'].append(timestamp)
            else:
                self.edges[edge_key] = {
                    'weight': 1,
                    'timestamps': [timestamp],
                    'first_seen': timestamp,
                    'last_seen': timestamp
                }
                
                self.graph.add_edge(sender, recipient, weight=1)
    
    def build_from_database(self, db_path: str, limit: int = None):
        """Build network from database"""
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # NOTE: recipients live in a separate table (see data_pipeline/database.py),
        # not a recipients_json column on emails -- joined and aggregated here.
        query = """
        SELECT e.message_id, e.sender, e.timestamp,
               GROUP_CONCAT(r.recipient_email, '|') AS recipients_list
        FROM emails e
        LEFT JOIN recipients r ON r.message_id = e.message_id
        GROUP BY e.message_id, e.sender, e.timestamp
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        rows = cursor.fetchall()

        logger.info(f"Building network from {len(rows)} emails...")

        for message_id, sender, timestamp_str, recipients_list in rows:
            recipients = recipients_list.split('|') if recipients_list else []
            timestamp = datetime.fromisoformat(timestamp_str)
            self.add_email(sender, recipients, timestamp)

        conn.close()
        
        # Update edge timestamps
        for edge_key, edge_data in self.edges.items():
            if edge_data['timestamps']:
                edge_data['first_seen'] = min(edge_data['timestamps'])
                edge_data['last_seen'] = max(edge_data['timestamps'])
        
        logger.info(f"Network built with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
    
    def analyze_sender_network(self, sender: str) -> Dict[str, Any]:
        """Analyze network position and relationships for a sender"""
        if sender not in self.graph:
            return {}
        
        analysis = {
            'sender': sender,
            'outdegree': self.graph.out_degree(sender),
            'indegree': self.graph.in_degree(sender),
            'total_degree': self.graph.degree(sender),
        }
        
        # Get top contacts
        out_edges = list(self.graph.out_edges(sender, data=True))
        out_edges_sorted = sorted(out_edges, key=lambda x: x[2].get('weight', 0), reverse=True)
        
        analysis['top_recipients'] = [
            {'recipient': recipient, 'weight': data.get('weight', 0)}
            for _, recipient, data in out_edges_sorted[:10]
        ]
        
        # Calculate communication diversity
        total_recipients = len(out_edges)
        if total_recipients > 0:
            weights = [data.get('weight', 0) for _, _, data in out_edges]
            entropy = -sum((w/sum(weights)) * np.log2(w/sum(weights)) for w in weights if w > 0)
            max_entropy = np.log2(total_recipients) if total_recipients > 0 else 0
            analysis['communication_entropy'] = entropy
            analysis['communication_diversity'] = entropy / max_entropy if max_entropy > 0 else 0
        
        # Calculate centrality measures
        try:
            analysis['betweenness_centrality'] = nx.betweenness_centrality(self.graph).get(sender, 0)
            analysis['closeness_centrality'] = nx.closeness_centrality(self.graph).get(sender, 0)
        except:
            analysis['betweenness_centrality'] = 0
            analysis['closeness_centrality'] = 0
        
        # Analyze recipient clusters
        analysis['recipient_clusters'] = self._analyze_recipient_clusters(sender)
        
        return analysis
    
    def _analyze_recipient_clusters(self, sender: str) -> List[Dict[str, Any]]:
        """Analyze clusters of recipients (who emails whom together)"""
        # Get all recipients of this sender
        recipients = [n for n in self.graph.successors(sender)]
        
        if len(recipients) < 2:
            return []
        
        # Create subgraph of recipients
        recipient_subgraph = self.graph.subgraph(recipients).to_undirected()
        
        # Find connected components (clusters)
        clusters = []
        for component in nx.connected_components(recipient_subgraph):
            if len(component) > 1:  # Only consider clusters with at least 2 nodes
                cluster = {
                    'members': list(component),
                    'size': len(component),
                    'density': nx.density(recipient_subgraph.subgraph(component))
                }
                clusters.append(cluster)
        
        return clusters
    
    def detect_anomalous_relationships(self, sender: str, recipient: str) -> Dict[str, Any]:
        """Detect if a relationship is anomalous"""
        edge_key = (sender, recipient)
        
        if edge_key not in self.edges:
            return {
                'is_anomalous': True,
                'reasons': ['No previous communication'],      # now a list, matches the other branch
                'confidence': 0.9,
                'edge_data': None         # now always present, None when no edge exists
            }
        
        edge_data = self.edges[edge_key]
        
        # Check if relationship is recent
        days_since_last = (datetime.now() - edge_data['last_seen']).days
        
        anomalies = []
        confidence = 0.0
        
        # Anomaly: Long time since last communication
        if days_since_last > 365:  # More than a year
            anomalies.append(f"No communication for {days_since_last} days")
            confidence = max(confidence, 0.7)
        
        # Anomaly: Very low frequency
        if edge_data['weight'] == 1 and days_since_last > 30:
            anomalies.append(f"Only one previous email, {days_since_last} days ago")
            confidence = max(confidence, 0.8)
        
        # Anomaly: Recipient is not in sender's top contacts
        sender_analysis = self.analyze_sender_network(sender)
        top_recipients = [r['recipient'] for r in sender_analysis.get('top_recipients', [])]
        
        if recipient not in top_recipients and len(top_recipients) >= 10:
            anomalies.append("Recipient not in top contacts")
            confidence = max(confidence, 0.6)
        
        return {
            'is_anomalous': len(anomalies) > 0,
            'reasons': anomalies,
            'confidence': confidence,
            'edge_data': edge_data
        }
    
    def visualize_network(self, output_path: str, highlight_nodes: List[str] = None):
        """Create visualization of the network"""
        plt.figure(figsize=(12, 10))
        
        # Use spring layout
        pos = nx.spring_layout(self.graph, k=0.3, iterations=50)
        
        # Draw nodes
        node_sizes = [self.nodes[node].get('email_count', 1) * 10 for node in self.graph.nodes()]
        node_colors = []
        
        for node in self.graph.nodes():
            if highlight_nodes and node in highlight_nodes:
                node_colors.append('red')
            elif self.nodes[node].get('type') == 'sender':
                node_colors.append('lightblue')
            else:
                node_colors.append('lightgreen')
        
        nx.draw_networkx_nodes(self.graph, pos, node_size=node_sizes, node_color=node_colors, alpha=0.8)
        
        # Draw edges with weights
        edge_weights = [self.edges.get((u, v), {}).get('weight', 1) for u, v in self.graph.edges()]
        nx.draw_networkx_edges(self.graph, pos, width=[w/5 for w in edge_weights], alpha=0.5)
        
        # Draw labels for important nodes
        important_nodes = [n for n in self.graph.nodes() if self.nodes[n].get('email_count', 0) > 10]
        labels = {node: node.split('@')[0] for node in important_nodes}
        nx.draw_networkx_labels(self.graph, pos, labels, font_size=8)
        
        plt.title("Email Communication Network")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Network visualization saved to {output_path}")
    
    def save_network(self, output_path: str):
        """Save network to JSON file"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # edges are keyed by (sender, recipient) tuples -- JSON can't use
        # tuple keys, so convert to strings here. load_network() already
        # expects string keys and converts them back via eval().
        serializable_edges = {str(key): value for key, value in self.edges.items()}

        network_data = {
            'nodes': self.nodes,
            'edges': serializable_edges,
            'graph_info': {
                'num_nodes': self.graph.number_of_nodes(),
                'num_edges': self.graph.number_of_edges(),
                'density': nx.density(self.graph)
            }
        }

        with open(output_path, 'w') as f:
            json.dump(network_data, f, indent=2, default=str)
        
        logger.info(f"Network saved to {output_path}")
    
    def load_network(self, input_path: str):
        """Load network from JSON file"""
        with open(input_path, 'r') as f:
            network_data = json.load(f)
        
        self.nodes = network_data['nodes']
        self.edges = {}
        
        # Rebuild graph
        self.graph = nx.DiGraph()
        
        # Add nodes
        for node, attrs in self.nodes.items():
            self.graph.add_node(node, **attrs)
        
        # Add edges
        for edge_key_str, edge_data in network_data['edges'].items():
            # Convert string key back to tuple
            edge_key = eval(edge_key_str)
            sender, recipient = edge_key
            
            # Convert timestamps
            if 'timestamps' in edge_data:
                edge_data['timestamps'] = [datetime.fromisoformat(ts) for ts in edge_data['timestamps']]
            if 'first_seen' in edge_data:
                edge_data['first_seen'] = datetime.fromisoformat(edge_data['first_seen'])
            if 'last_seen' in edge_data:
                edge_data['last_seen'] = datetime.fromisoformat(edge_data['last_seen'])
            
            self.edges[edge_key] = edge_data
            self.graph.add_edge(sender, recipient, weight=edge_data.get('weight', 1))
        
        logger.info(f"Network loaded with {self.graph.number_of_nodes()} nodes")