try:
    from manga_panels.detect import Box, Detector, XYCutDetector, MLDetector, get_detector
    from manga_panels.pipeline import process_archive
    __all__ = [
        "Box", "Detector", "XYCutDetector", "MLDetector", "get_detector",
        "process_archive",
    ]
except ImportError:
    # Allow archive module to be imported without detect/pipeline dependencies
    __all__ = []
