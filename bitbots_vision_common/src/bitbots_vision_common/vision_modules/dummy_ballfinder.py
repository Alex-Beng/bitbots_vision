from .candidate import CandidateFinder


class DummyClassifier(CandidateFinder):
    def __init__(self, classifier, stuff):
        self._classified_candidates = []
        self._sorted_candidates = []
        self._top_candidate = None

    def set_image(self, image):
        pass

    def get_candidates(self):
        return self._classified_candidates

    def get_top_candidates(self, count=1):
        return self._sorted_candidates
