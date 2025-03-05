import csv
from datetime import datetime
from pathlib import Path

class ResultWriter:
    def __init__(self, filename):
        """Initialize ResultWriter with output filename"""
        self.results_dir = Path('results')
        self.results_dir.mkdir(exist_ok=True)
        self.filepath = self.results_dir / filename
        
    def write_results(self, results):
        """Write test results to CSV file."""
        fieldnames = ['scenario', 'status', 'details', 'timestamp']
        with open(self.filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for result in results:
                result['timestamp'] = timestamp
                writer.writerow(result)