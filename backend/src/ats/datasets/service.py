"""The immutable XAUUSD dataset registry."""

from ats.datasets.ingestion import XauUsdDatasetStore

DatasetRegistryService = XauUsdDatasetStore


def get_dataset_registry_service() -> XauUsdDatasetStore:
    return XauUsdDatasetStore()
