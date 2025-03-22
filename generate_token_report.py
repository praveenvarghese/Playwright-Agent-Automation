import os
import json
import matplotlib.pyplot as plt
from datetime import datetime
import glob

def generate_monthly_usage_report():
    """
    Generate a comprehensive report of monthly token usage.
    """
    # Get all monthly usage files
    usage_files = glob.glob('usage_stats_*.json')
    if not usage_files:
        print("No usage statistics files found.")
        return
    
    # Sort files by month
    usage_files.sort()
    
    # Collect data from all files
    monthly_data = []
    for file_path in usage_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                monthly_data.append(data)
        except Exception as e:
            print(f"Error reading {file_path}: {str(e)}")
    
    if not monthly_data:
        print("No valid data found in usage files.")
        return
    
    # Create output directory for reports
    output_dir = "token_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate summary file
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    summary_file = os.path.join(output_dir, f"token_usage_summary_{timestamp}.json")
    with open(summary_file, 'w') as f:
        json.dump(monthly_data, f, indent=2)
    
    # Extract data for plotting
    months = [data['month'] for data in monthly_data]
    embedding_tokens = [data['embedding_tokens'] for data in monthly_data]
    completion_input = [data['completion_tokens_input'] for data in monthly_data]
    completion_output = [data['completion_tokens_output'] for data in monthly_data]
    costs = [data['estimated_cost'] for data in monthly_data]
    
    # Create plots
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Token usage by type
    plt.subplot(2, 1, 1)
    plt.bar(months, embedding_tokens, label='Embedding Tokens')
    plt.bar(months, completion_input, bottom=embedding_tokens, label='Completion Input')
    plt.bar(months, completion_output, bottom=[i+j for i,j in zip(embedding_tokens, completion_input)], label='Completion Output')
    plt.title('Monthly Token Usage by Type')
    plt.xlabel('Month')
    plt.ylabel('Number of Tokens')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Plot 2: Cost over time
    plt.subplot(2, 1, 2)
    plt.plot(months, costs, marker='o', linestyle='-', color='red')
    plt.title('Monthly Cost Estimate')
    plt.xlabel('Month')
    plt.ylabel('Cost (USD)')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Adjust layout and save
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"token_usage_charts_{timestamp}.png"))
    
    print(f"Monthly usage report generated in {output_dir} directory.")
    print(f"Summary file: {summary_file}")
    print(f"Charts: token_usage_charts_{timestamp}.png")

def get_session_reports():
    """
    Compile session reports from individual session logs.
    """
    # Get all token usage report files
    report_files = glob.glob('token_usage_report_*.json')
    if not report_files:
        print("No session report files found.")
        return
    
    # Sort by timestamp
    report_files.sort()
    
    # Collect session data
    session_data = []
    for file_path in report_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if 'session' in data:
                    session_entry = {
                        'timestamp': os.path.basename(file_path).replace('token_usage_report_', '').replace('.json', ''),
                        'session_data': data['session']
                    }
                    session_data.append(session_entry)
        except Exception as e:
            print(f"Error reading {file_path}: {str(e)}")
    
    if not session_data:
        print("No valid session data found.")
        return
    
    # Create output directory for reports
    output_dir = "token_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate session summary file
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    session_summary_file = os.path.join(output_dir, f"session_summary_{timestamp}.json")
    with open(session_summary_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"Session summary report generated: {session_summary_file}")
    
    # Extract data for analysis
    timestamps = [entry['timestamp'] for entry in session_data]
    costs = [entry['session_data']['estimated_cost'] for entry in session_data]
    durations = [entry['session_data'].get('duration_seconds', 0) for entry in session_data]
    api_calls = [entry['session_data']['api_calls'] for entry in session_data]
    
    # Create session charts
    plt.figure(figsize=(12, 10))
    
    # Plot 1: Session costs
    plt.subplot(3, 1, 1)
    plt.bar(range(len(timestamps)), costs)
    plt.title('Session Costs')
    plt.xlabel('Session Index')
    plt.ylabel('Cost (USD)')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Plot 2: Session durations
    plt.subplot(3, 1, 2)
    plt.bar(range(len(timestamps)), durations)
    plt.title('Session Durations')
    plt.xlabel('Session Index')
    plt.ylabel('Duration (seconds)')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Plot 3: API calls per session
    plt.subplot(3, 1, 3)
    plt.bar(range(len(timestamps)), api_calls)
    plt.title('API Calls per Session')
    plt.xlabel('Session Index')
    plt.ylabel('Number of API Calls')
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Adjust layout and save
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"session_charts_{timestamp}.png"))
    
    print(f"Session charts generated: session_charts_{timestamp}.png")

if __name__ == "__main__":
    print("Generating token usage reports...")
    
    # Generate monthly usage report
    generate_monthly_usage_report()
    
    # Generate session reports
    get_session_reports()
    
    print("Report generation complete.")