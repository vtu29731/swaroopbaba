"""Small NumPy regressors used when Windows blocks scikit-learn native tree DLLs."""

import numpy as np


class NumpyTreeRegressor:
    def __init__(self, max_depth=8, min_samples_leaf=6, max_features=None, random_state=42):
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state

    def fit(self, x, y):
        self.x = np.asarray(x.toarray() if hasattr(x, "toarray") else x, dtype=np.float64)
        self.y = np.asarray(y, dtype=np.float64)
        self.rng = np.random.default_rng(self.random_state)
        self.feature_count = self.x.shape[1]
        self.root = self._build(np.arange(len(self.y)), 0)
        return self

    def _build(self, indices, depth):
        target = self.y[indices]
        node = {"value": float(np.mean(target))}
        if depth >= self.max_depth or len(indices) < 2 * self.min_samples_leaf:
            return node

        if self.max_features == "sqrt":
            count = max(1, int(np.sqrt(self.feature_count)))
        elif isinstance(self.max_features, int):
            count = min(self.max_features, self.feature_count)
        else:
            count = self.feature_count
        features = self.rng.choice(self.feature_count, size=count, replace=False)
        best_error = float(np.sum((target - node["value"]) ** 2))
        best_split = None

        for feature in features:
            values = self.x[indices, feature]
            order = np.argsort(values)
            sorted_values = values[order]
            sorted_target = target[order]
            low, high = self.min_samples_leaf, len(indices) - self.min_samples_leaf
            if high < low:
                continue
            candidates = np.unique(np.quantile(sorted_values, np.linspace(0.1, 0.9, 9)))
            cumulative = np.cumsum(sorted_target)
            cumulative_sq = np.cumsum(sorted_target * sorted_target)
            for threshold in candidates:
                left_count = int(np.searchsorted(sorted_values, threshold, side="right"))
                if left_count < low or left_count > high:
                    continue
                right_count = len(indices) - left_count
                left_sum = cumulative[left_count - 1]
                right_sum = cumulative[-1] - left_sum
                left_sq = cumulative_sq[left_count - 1]
                right_sq = cumulative_sq[-1] - left_sq
                error = (left_sq - left_sum * left_sum / left_count)
                error += right_sq - right_sum * right_sum / right_count
                if error < best_error:
                    best_error = float(error)
                    best_split = (int(feature), float(threshold), order, left_count)

        if best_split is None:
            return node
        feature, threshold, order, left_count = best_split
        node["feature"] = feature
        node["threshold"] = threshold
        node["left"] = self._build(indices[order[:left_count]], depth + 1)
        node["right"] = self._build(indices[order[left_count:]], depth + 1)
        return node

    def _predict_one(self, row):
        node = self.root
        while "feature" in node:
            node = node["left"] if row[node["feature"]] <= node["threshold"] else node["right"]
        return node["value"]

    def predict(self, x):
        matrix = np.asarray(x.toarray() if hasattr(x, "toarray") else x, dtype=np.float64)
        return np.fromiter((self._predict_one(row) for row in matrix), dtype=np.float64, count=len(matrix))


class NumpyForestRegressor:
    def __init__(self, n_estimators=28, random_state=42):
        self.n_estimators = n_estimators
        self.random_state = random_state

    def fit(self, x, y):
        matrix = np.asarray(x.toarray() if hasattr(x, "toarray") else x, dtype=np.float64)
        target = np.asarray(y, dtype=np.float64)
        rng = np.random.default_rng(self.random_state)
        self.trees = []
        for _ in range(self.n_estimators):
            sample = rng.integers(0, len(target), size=len(target))
            tree = NumpyTreeRegressor(
                max_depth=9, min_samples_leaf=8, max_features="sqrt",
                random_state=int(rng.integers(0, 2**31 - 1)),
            )
            tree.fit(matrix[sample], target[sample])
            self.trees.append(tree)
        return self

    def predict(self, x):
        return np.mean([tree.predict(x) for tree in self.trees], axis=0)


class NumpyBoostingRegressor:
    def __init__(self, n_estimators=36, learning_rate=0.07, random_state=42):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.random_state = random_state

    def fit(self, x, y):
        matrix = np.asarray(x.toarray() if hasattr(x, "toarray") else x, dtype=np.float64)
        target = np.asarray(y, dtype=np.float64)
        self.initial_value = float(np.mean(target))
        fitted = np.full(len(target), self.initial_value)
        rng = np.random.default_rng(self.random_state)
        self.trees = []
        for _ in range(self.n_estimators):
            tree = NumpyTreeRegressor(
                max_depth=2, min_samples_leaf=16, max_features=None,
                random_state=int(rng.integers(0, 2**31 - 1)),
            ).fit(matrix, target - fitted)
            self.trees.append(tree)
            fitted += self.learning_rate * tree.predict(matrix)
        return self

    def predict(self, x):
        prediction = np.full(x.shape[0], self.initial_value, dtype=np.float64)
        for tree in self.trees:
            prediction += self.learning_rate * tree.predict(x)
        return prediction
