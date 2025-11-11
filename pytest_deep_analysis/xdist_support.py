"""
Support for pytest-xdist parallel test execution.

This module provides utilities for serializing and merging fixture graph
state across parallel workers when using pytest-xdist. This allows the
linter to correctly analyze fixtures even when tests are distributed
across multiple processes.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional


class FixtureGraphSerializer:
    """Serializes and deserializes fixture graph data for parallel execution."""

    @staticmethod
    def serialize_fixture_info(fixture_info: Any) -> Dict[str, Any]:
        """Serialize a FixtureInfo object to a dictionary.

        Args:
            fixture_info: FixtureInfo instance to serialize

        Returns:
            Dictionary representation of the fixture info
        """
        return {
            "name": fixture_info.name,
            "scope": fixture_info.scope,
            "autouse": fixture_info.autouse,
            "dependencies": fixture_info.dependencies,
            "file_path": fixture_info.file_path,
            "used_by": list(fixture_info.used_by),
            # Note: We don't serialize the AST node as it's not JSON-serializable
        }

    @staticmethod
    def serialize_fixture_graph(
        fixture_graph: Dict[str, Any], test_fixture_usage: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Serialize the complete fixture graph.

        Args:
            fixture_graph: Dictionary mapping fixture names to FixtureInfo
            test_fixture_usage: Dictionary mapping test names to fixture lists

        Returns:
            Serializable dictionary representation
        """
        serialized_fixtures = {}
        for name, info in fixture_graph.items():
            serialized_fixtures[name] = FixtureGraphSerializer.serialize_fixture_info(
                info
            )

        return {
            "fixtures": serialized_fixtures,
            "test_usage": test_fixture_usage,
        }

    @staticmethod
    def save_fixture_graph(
        fixture_graph: Dict[str, Any],
        test_fixture_usage: Dict[str, List[str]],
        output_path: str,
    ) -> None:
        """Save fixture graph to a JSON file.

        Args:
            fixture_graph: Dictionary mapping fixture names to FixtureInfo
            test_fixture_usage: Dictionary mapping test names to fixture lists
            output_path: Path to save the JSON file
        """
        data = FixtureGraphSerializer.serialize_fixture_graph(
            fixture_graph, test_fixture_usage
        )

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load_fixture_graph(input_path: str) -> Dict[str, Any]:
        """Load fixture graph from a JSON file.

        Args:
            input_path: Path to the JSON file

        Returns:
            Dictionary with 'fixtures' and 'test_usage' keys
        """
        with open(input_path, "r") as f:
            return json.load(f)

    @staticmethod
    def merge_fixture_graphs(graphs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple fixture graphs from parallel workers.

        This is used to combine fixture analysis results from multiple
        pytest-xdist workers into a single comprehensive graph.

        Args:
            graphs: List of serialized fixture graphs

        Returns:
            Merged fixture graph
        """
        merged_fixtures: Dict[str, Dict[str, Any]] = {}
        merged_test_usage: Dict[str, List[str]] = {}

        for graph in graphs:
            # Merge fixtures
            for name, info in graph.get("fixtures", {}).items():
                if name not in merged_fixtures:
                    merged_fixtures[name] = info.copy()
                else:
                    # Merge used_by sets
                    existing = set(merged_fixtures[name].get("used_by", []))
                    new = set(info.get("used_by", []))
                    merged_fixtures[name]["used_by"] = list(existing | new)

            # Merge test usage
            for test_name, fixtures in graph.get("test_usage", {}).items():
                if test_name not in merged_test_usage:
                    merged_test_usage[test_name] = fixtures
                else:
                    # Combine fixture lists, removing duplicates
                    existing = set(merged_test_usage[test_name])
                    new = set(fixtures)
                    merged_test_usage[test_name] = list(existing | new)

        return {
            "fixtures": merged_fixtures,
            "test_usage": merged_test_usage,
        }


class XdistCoordinator:
    """Coordinates fixture analysis across pytest-xdist workers."""

    def __init__(self, output_dir: str = ".pytest-deep-analysis"):
        """Initialize the coordinator.

        Args:
            output_dir: Directory to store worker results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_worker_output_path(self, worker_id: str) -> Path:
        """Get the output path for a specific worker.

        Args:
            worker_id: Unique identifier for the worker

        Returns:
            Path to the worker's output file
        """
        return self.output_dir / f"worker_{worker_id}.json"

    def save_worker_results(
        self,
        worker_id: str,
        fixture_graph: Dict[str, Any],
        test_fixture_usage: Dict[str, List[str]],
    ) -> None:
        """Save results from a single worker.

        Args:
            worker_id: Unique identifier for the worker
            fixture_graph: The worker's fixture graph
            test_fixture_usage: The worker's test fixture usage
        """
        output_path = self.get_worker_output_path(worker_id)
        FixtureGraphSerializer.save_fixture_graph(
            fixture_graph, test_fixture_usage, str(output_path)
        )

    def collect_worker_results(self) -> List[Dict[str, Any]]:
        """Collect results from all workers.

        Returns:
            List of fixture graphs from all workers
        """
        graphs = []
        for worker_file in self.output_dir.glob("worker_*.json"):
            try:
                graph = FixtureGraphSerializer.load_fixture_graph(str(worker_file))
                graphs.append(graph)
            except Exception:
                # Skip invalid files
                continue
        return graphs

    def merge_all_results(self) -> Dict[str, Any]:
        """Merge results from all workers.

        Returns:
            Merged fixture graph containing all worker results
        """
        graphs = self.collect_worker_results()
        return FixtureGraphSerializer.merge_fixture_graphs(graphs)

    def cleanup(self) -> None:
        """Clean up worker result files."""
        for worker_file in self.output_dir.glob("worker_*.json"):
            try:
                worker_file.unlink()
            except Exception:
                pass

        # Try to remove the directory if empty
        try:
            self.output_dir.rmdir()
        except Exception:
            pass


def is_xdist_worker() -> bool:
    """Check if running as a pytest-xdist worker.

    Returns:
        True if running as an xdist worker, False otherwise
    """
    import os

    return "PYTEST_XDIST_WORKER" in os.environ


def get_worker_id() -> Optional[str]:
    """Get the current xdist worker ID.

    Returns:
        Worker ID if running as an xdist worker, None otherwise
    """
    import os

    return os.environ.get("PYTEST_XDIST_WORKER")
