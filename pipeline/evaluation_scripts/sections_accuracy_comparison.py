import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


class HierarchyAccuracyCalculator:
    """
    A class to compare two hierarchy JSON files and calculate accuracy metrics.
    """

    def __init__(self, ground_truth_file: str, extracted_file: str):
        """
        Initialize with ground truth and extracted hierarchy JSON files.

        Args:
            ground_truth_file: Path to the ground truth JSON file
            extracted_file: Path to the extracted hierarchy JSON file
        """
        self.ground_truth_file = Path(ground_truth_file)
        self.extracted_file = Path(extracted_file)

        # Validate files exist
        if not self.ground_truth_file.exists():
            raise FileNotFoundError(f"Ground truth file not found: {ground_truth_file}")
        if not self.extracted_file.exists():
            raise FileNotFoundError(f"Extracted file not found: {extracted_file}")

        # Load JSON files
        with open(self.ground_truth_file, "r", encoding="utf-8") as f:
            self.ground_truth = json.load(f)

        with open(self.extracted_file, "r", encoding="utf-8") as f:
            self.extracted = json.load(f)

    def _flatten_hierarchy(
        self, hierarchy: Dict, parent_path: str = ""
    ) -> List[Tuple[str, int]]:
        """
        Flatten a nested hierarchy into a list of (full_path, level) tuples.
        Level 0 = top-level/parent sections, Level 1 = first children, etc.

        Args:
            hierarchy: Nested dictionary hierarchy
            parent_path: Current path in the hierarchy

        Returns:
            List of (path, level) tuples where level starts at 0
        """
        result = []
        for key, value in hierarchy.items():
            current_path = f"{parent_path} > {key}" if parent_path else key
            level = current_path.count(" > ")  # ✅ FIXED
            result.append((current_path, level))
            if value:
                result.extend(self._flatten_hierarchy(value, current_path))
        return result

    def _get_all_sections(self, hierarchy: Dict) -> Set[str]:
        """
        Get all section names (without path) from hierarchy.

        Args:
            hierarchy: Nested dictionary hierarchy

        Returns:
            Set of all section names
        """
        sections = set()
        for key, value in hierarchy.items():
            sections.add(key)
            if value:
                sections.update(self._get_all_sections(value))
        return sections

    def _get_section_paths(self, hierarchy: Dict) -> Set[str]:
        """
        Get all full paths from hierarchy.

        Args:
            hierarchy: Nested dictionary hierarchy

        Returns:
            Set of all full paths
        """
        flat = self._flatten_hierarchy(hierarchy)
        return {path for path, _ in flat}

    def calculate_section_accuracy(self) -> Dict[str, float]:
        """
        Calculate accuracy metrics for sections (ignoring hierarchy).

        Returns:
            Dictionary with precision, recall, and f1_score
        """
        gt_sections = self._get_all_sections(self.ground_truth)
        ex_sections = self._get_all_sections(self.extracted)

        true_positives = len(gt_sections & ex_sections)
        false_positives = len(ex_sections - gt_sections)
        false_negatives = len(gt_sections - ex_sections)

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0
        )
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        }

    def calculate_hierarchy_accuracy(self) -> Dict[str, float]:
        """
        Calculate accuracy metrics for full hierarchy paths (considering structure).

        Returns:
            Dictionary with precision, recall, and f1_score
        """
        gt_paths = self._get_section_paths(self.ground_truth)
        ex_paths = self._get_section_paths(self.extracted)

        true_positives = len(gt_paths & ex_paths)
        false_positives = len(ex_paths - gt_paths)
        false_negatives = len(gt_paths - ex_paths)

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0
        )
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        }

    def calculate_level_accuracy(self) -> Dict[str, Dict]:
        """
        Calculate accuracy for each hierarchy level.

        Returns:
            Dictionary with accuracy metrics per level
        """
        gt_flat = self._flatten_hierarchy(self.ground_truth)
        ex_flat = self._flatten_hierarchy(self.extracted)

        # Group by level
        gt_by_level = {}
        ex_by_level = {}

        for path, level in gt_flat:
            if level not in gt_by_level:
                gt_by_level[level] = set()
            gt_by_level[level].add(path)

        for path, level in ex_flat:
            if level not in ex_by_level:
                ex_by_level[level] = set()
            ex_by_level[level].add(path)

        # Calculate metrics per level
        all_levels = set(gt_by_level.keys()) | set(ex_by_level.keys())
        level_metrics = {}

        for level in sorted(all_levels):
            gt_set = gt_by_level.get(level, set())
            ex_set = ex_by_level.get(level, set())

            tp = len(gt_set & ex_set)
            fp = len(ex_set - gt_set)
            fn = len(gt_set - ex_set)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = (
                2 * (precision * recall) / (precision + recall)
                if (precision + recall) > 0
                else 0
            )

            level_metrics[f"level_{level}"] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "count_gt": len(gt_set),
                "count_extracted": len(ex_set),
            }

        return level_metrics

    def get_missing_sections(self) -> List[str]:
        """
        Get sections that are in ground truth but missing in extracted.

        Returns:
            List of missing section paths
        """
        gt_paths = self._get_section_paths(self.ground_truth)
        ex_paths = self._get_section_paths(self.extracted)
        return sorted(list(gt_paths - ex_paths))

    def get_extra_sections(self) -> List[str]:
        """
        Get sections that are in extracted but not in ground truth.

        Returns:
            List of extra section paths
        """
        gt_paths = self._get_section_paths(self.ground_truth)
        ex_paths = self._get_section_paths(self.extracted)
        return sorted(list(ex_paths - gt_paths))

    def generate_report(self) -> Dict:
        """
        Generate a comprehensive accuracy report.

        Returns:
            Dictionary containing all metrics and analysis
        """
        report = {
            "files": {
                "ground_truth": str(self.ground_truth_file),
                "extracted": str(self.extracted_file),
            },
            "section_accuracy": self.calculate_section_accuracy(),
            "hierarchy_accuracy": self.calculate_hierarchy_accuracy(),
            "level_accuracy": self.calculate_level_accuracy(),
            "missing_sections": self.get_missing_sections(),
            "extra_sections": self.get_extra_sections(),
            "summary": {
                "total_sections_gt": len(self._get_all_sections(self.ground_truth)),
                "total_sections_extracted": len(self._get_all_sections(self.extracted)),
                "total_paths_gt": len(self._get_section_paths(self.ground_truth)),
                "total_paths_extracted": len(self._get_section_paths(self.extracted)),
            },
        }

        return report

    def print_report(self):
        """
        Print a formatted accuracy report.
        """
        report = self.generate_report()

        print("=" * 80)
        print("HIERARCHY ACCURACY REPORT")
        print("=" * 80)
        print(f"\nGround Truth File: {report['files']['ground_truth']}")
        print(f"Extracted File: {report['files']['extracted']}")

        print("\n" + "-" * 80)
        print("SECTION ACCURACY (Names Only, Ignoring Hierarchy)")
        print("-" * 80)
        sa = report["section_accuracy"]
        print(f"Precision: {sa['precision']:.2%}")
        print(f"Recall: {sa['recall']:.2%}")
        print(f"F1-Score: {sa['f1_score']:.2%}")
        print(f"True Positives: {sa['true_positives']}")
        print(f"False Positives: {sa['false_positives']}")
        print(f"False Negatives: {sa['false_negatives']}")

        print("\n" + "-" * 80)
        print("HIERARCHY ACCURACY (Full Paths, Including Structure)")
        print("-" * 80)
        ha = report["hierarchy_accuracy"]
        print(f"Precision: {ha['precision']:.2%}")
        print(f"Recall: {ha['recall']:.2%}")
        print(f"F1-Score: {ha['f1_score']:.2%}")
        print(f"True Positives: {ha['true_positives']}")
        print(f"False Positives: {ha['false_positives']}")
        print(f"False Negatives: {ha['false_negatives']}")

        print("\n" + "-" * 80)
        print("LEVEL-WISE ACCURACY")
        print("-" * 80)
        for level, metrics in report["level_accuracy"].items():
            print(f"\n{level.upper()}:")
            print(f"  Precision: {metrics['precision']:.2%}")
            print(f"  Recall: {metrics['recall']:.2%}")
            print(f"  F1-Score: {metrics['f1_score']:.2%}")
            print(
                f"  Count (GT/Extracted): {metrics['count_gt']}/{metrics['count_extracted']}"
            )

        if report["missing_sections"]:
            print("\n" + "-" * 80)
            print("MISSING SECTIONS (In Ground Truth but Not Extracted)")
            print("-" * 80)
            for section in report["missing_sections"][:10]:  # Show first 10
                print(f"  - {section}")
            if len(report["missing_sections"]) > 10:
                print(f"  ... and {len(report['missing_sections']) - 10} more")

        if report["extra_sections"]:
            print("\n" + "-" * 80)
            print("EXTRA SECTIONS (In Extracted but Not Ground Truth)")
            print("-" * 80)
            for section in report["extra_sections"][:10]:  # Show first 10
                print(f"  - {section}")
            if len(report["extra_sections"]) > 10:
                print(f"  ... and {len(report['extra_sections']) - 10} more")

        print("\n" + "-" * 80)
        print("SUMMARY")
        print("-" * 80)
        summary = report["summary"]
        print(f"Total Sections (GT): {summary['total_sections_gt']}")
        print(f"Total Sections (Extracted): {summary['total_sections_extracted']}")
        print(f"Total Paths (GT): {summary['total_paths_gt']}")
        print(f"Total Paths (Extracted): {summary['total_paths_extracted']}")
        print("=" * 80)

    def save_report(self, output_file: str = "accuracy_report.json"):
        """
        Save the accuracy report to a JSON file.

        Args:
            output_file: Path for the output report file
        """
        report = self.generate_report()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nReport saved to: {output_file}")


# Example usage
if __name__ == "__main__":

    # Calculate accuracy
    calculator = HierarchyAccuracyCalculator(
        ground_truth_file="ground_truth_hierarchy.json",
        extracted_file="AP510e_Installation_Guide_fixed_hierarchy.json",
    )

    # Print report
    calculator.print_report()

    # Save report to file
    calculator.save_report("accuracy_report.json")
