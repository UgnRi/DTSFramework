import csv
from datetime import datetime
from pathlib import Path


class ResultWriter:
    def __init__(self, filename):
        """Initialize ResultWriter with output filename"""
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.filepath = self.results_dir / filename

    def write_results(self, results):
        """Write test results to CSV file."""
        fieldnames = ["scenario", "status", "details", "timestamp"]
        with open(self.filepath, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for result in results:
                result_with_timestamp = result.copy()
                result_with_timestamp["timestamp"] = timestamp
                writer.writerow(result_with_timestamp)

    def write_organized_results(self, organized_results):
        """Write results organized by test type to a CSV file"""
        fieldnames = ["scenario", "status", "details", "timestamp"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Write a header for the entire file
            writer.writerow(["Test Results Summary"])
            writer.writerow([])

            # Process each test type section
            for section_name, section_results in organized_results.items():
                if not section_results:
                    continue

                # Write section header
                writer.writerow([section_name])
                writer.writerow(fieldnames)

                # Write results for this section
                for result in section_results:
                    result_copy = result.copy()
                    result_copy["timestamp"] = timestamp
                    writer.writerow(
                        [
                            result_copy.get("scenario", ""),
                            result_copy.get("status", ""),
                            str(result_copy.get("details", "")),
                            result_copy.get("timestamp", ""),
                        ]
                    )

                # Add a blank row between sections
                writer.writerow([])

            # Write summary statistics
            all_results = []
            for results in organized_results.values():
                all_results.extend(results)

            total_tests = len(all_results)
            passed_tests = sum(1 for r in all_results if r.get("status") == "PASS")
            failed_tests = total_tests - passed_tests

            writer.writerow(["Summary"])
            writer.writerow(["Total Tests", "Passed Tests", "Failed Tests"])
            writer.writerow([total_tests, passed_tests, failed_tests])
