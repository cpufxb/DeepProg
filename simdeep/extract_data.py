""" """
from sklearn.preprocessing import Normalizer
from sklearn.preprocessing import RobustScaler
from sklearn.preprocessing import MinMaxScaler

from simdeep.config import TRAINING_TSV
from simdeep.config import TEST_TSV
from simdeep.config import SURVIVAL_TSV
from simdeep.config import SURVIVAL_TSV_TEST
from simdeep.config import PATH_DATA

from simdeep.config import TRAIN_MIN_MAX
from simdeep.config import TRAIN_NORM_SCALE
from simdeep.config import TRAIN_CORR_REDUCTION
from simdeep.config import TRAIN_RANK_NORM
from simdeep.config import TRAIN_MAD_SCALE
from simdeep.config import TRAIN_ROBUST_SCALE
from simdeep.config import TRAIN_CORR_RANK_NORM

from simdeep.config import CROSS_VALIDATION_INSTANCE
from simdeep.config import TEST_FOLD

from simdeep.survival_utils import load_data_from_tsv
from simdeep.survival_utils import load_survival_file
from simdeep.survival_utils import MadScaler
from simdeep.survival_utils import RankNorm
from simdeep.survival_utils import CorrelationReducer

from time import time

import numpy as np


def main():
    """ """
    load_data = LoadData()
    load_data.load_array()
    load_data.load_survival()
    load_data.create_a_cv_split()

    load_data.normalize_training_array()

    load_data.load_matrix_test_fold()

    load_data.load_matrix_test()
    load_data.load_survival_test()


class LoadData():
    def __init__(
            self,
            path_data=PATH_DATA,
            training_tsv=TRAINING_TSV,
            test_tsv=TEST_TSV,
            survival_tsv=SURVIVAL_TSV,
            survival_tsv_test=SURVIVAL_TSV_TEST,
            cross_validation_instance=CROSS_VALIDATION_INSTANCE,
            test_fold=TEST_FOLD,
    ):
        """
        class to extract data
        :training_matrices: dict(matrice_type, path to the tsv file)

        :path_data: str    path to the folder containing the data
        :training_tsv: dict    dict('data type', 'name of the tsv file')
        :survival_tsv: str    name of the tsv file containing the survival data
                              of the training set
        :survival_tsv_test: str    name of the tsv file containing the survival data
                                   of the test set
        :tsv_test: str    name of the file containing the test dataset
        :data_type_test: str    name of the data type of the test set
                                must match a key existing in training_tsv
        """

        self.path_data = path_data
        self.survival_tsv = survival_tsv
        self.training_tsv = training_tsv
        self.feature_array = {}
        self.matrix_array = {}

        self.test_tsv = test_tsv
        self.matrix_array_train = {}

        self.sample_ids = []
        self.data_type = training_tsv.keys()

        self.survival = None

        self.survival_tsv_test = survival_tsv_test

        self.feature_test_array = {}
        self.matrix_test_array = {}

        self.sample_ids_cv = []
        self.matrix_cv_array = {}
        self.survival_cv = None

        self.matrix_ref_array = {}
        self.feature_ref_array = {}

        self.survival_test = None
        self.sample_ids_test = None

        self.cross_validation_instance = cross_validation_instance
        self.test_fold = test_fold

        self.do_feature_reduction = None

        self.normalizer = Normalizer()
        self.mad_scaler = MadScaler()
        self.robust_scaler = RobustScaler()
        self.min_max_scaler = MinMaxScaler()
        self.dim_reducer = CorrelationReducer()

    def load_matrix_test_fold(self):
        """ """
        for key in self.test_tsv:

            matrix_test = self.matrix_cv_array[key].copy()
            matrix_ref = self.matrix_array[key].copy()

            matrix_ref, matrix_test = self.transform_matrices(
                matrix_ref, matrix_test, key,
                unit_norm=TRAIN_NORM_SCALE,
                rank_scale=TRAIN_RANK_NORM,
                mad_scale=TRAIN_MAD_SCALE,
                robust_scale=TRAIN_ROBUST_SCALE,
                min_max_scale=TRAIN_MIN_MAX,
                correlation_reducer=TRAIN_CORR_REDUCTION,
                corr_rank_scale=TRAIN_CORR_RANK_NORM,
            )

            self.matrix_cv_array[key] = matrix_test
            self.feature_ref_array[key] = self.feature_array[key][:]

    def load_matrix_test(self):
        """ """
        for key in self.test_tsv:
            self.feature_ref_array[key] = self.feature_array[key][:]
            sample_ids, feature_ids, matrix = load_data_from_tsv(self.test_tsv[key],
                                                             path_data=self.path_data)

            feature_ids_ref = self.feature_array[key]
            matrix_ref = self.matrix_array[key]

            common_features = set(feature_ids).intersection(feature_ids_ref)

            feature_ids_dict = {feat: i for i,feat in enumerate(feature_ids)}
            feature_ids_ref_dict = {feat: i for i,feat in enumerate(feature_ids_ref)}

            feature_index = [feature_ids_dict[feature] for feature in common_features]
            feature_ref_index = [feature_ids_ref_dict[feature] for feature in common_features]

            matrix_test = np.nan_to_num(matrix.T[feature_index].T)
            matrix_ref = np.nan_to_num(matrix_ref.T[feature_ref_index].T)

            self.feature_test_array[key] = list(common_features)

            if not isinstance(self.sample_ids_test, type(None)):
                assert(self.sample_ids_test == sample_ids)
            else:
                self.sample_ids_test = sample_ids

            matrix_ref, matrix_test = self.transform_matrices(
                matrix_ref, matrix_test, key,
                unit_norm=TRAIN_NORM_SCALE,
                rank_scale=TRAIN_RANK_NORM,
                mad_scale=TRAIN_MAD_SCALE,
                robust_scale=TRAIN_ROBUST_SCALE,
                min_max_scale=TRAIN_MIN_MAX,
                correlation_reducer=TRAIN_CORR_REDUCTION,
                corr_rank_scale=TRAIN_CORR_RANK_NORM,
            )

            self.matrix_test_array[key] = matrix_test
            self.matrix_ref_array[key] = matrix_ref

    def reorder_test_matrix(self, key):
        """ """
        features_test = self.feature_test_array[key]
        features_ref = self.feature_ref_array[key]

        ref_dict = {feat: pos for pos, feat in enumerate(features_test)}
        index = [ref_dict[feat] for feat in features_ref]

        self.feature_test_array[key] = features_ref[:]

        self.matrix_test_array[key] = self.matrix_test_array[key].T[index].T
        self.matrix_ref_array[key] = self.matrix_ref_array[key].T[index].T

    def load_array(self):
        """ """
        print('loading data...')
        t = time()

        self.feature_array = {}
        self.matrix_array = {}

        data = self.data_type[0]
        f_name = self.training_tsv[data]

        self.sample_ids, feature_ids, matrix = load_data_from_tsv(f_name,
                                                                  path_data=self.path_data)
        print('{0} loaded of dim:{1}'.format(f_name, matrix.shape))

        self.feature_array[data] = feature_ids
        self.matrix_array[data] = matrix

        for data in self.data_type[1:]:
            f_name = self.training_tsv[data]
            sample_ids, feature_ids, matrix = load_data_from_tsv(f_name,
                                                                 path_data=self.path_data)
            assert(self.sample_ids == sample_ids)

            self.feature_array[data] = feature_ids
            self.matrix_array[data] = matrix

            print('{0} loaded of dim:{1}'.format(f_name, matrix.shape))

        print('data loaded in {0} s'.format(time() - t))

    def create_a_cv_split(self):
        """ """
        if not self.cross_validation_instance:
            return

        cv = self.cross_validation_instance
        train, test = [(tn, tt) for tn, tt in cv.split(self.sample_ids)][self.test_fold]

        for key in self.matrix_array:
            self.matrix_cv_array[key] = self.matrix_array[key][test]
            self.matrix_array[key] = self.matrix_array[key][train]

        self.survival_test = self.survival.copy()[test]
        self.survival = self.survival[train]

        self.sample_ids_cv = np.asarray(self.sample_ids)[test].tolist()
        self.sample_ids = np.asarray(self.sample_ids)[train].tolist()

    def load_survival(self):
        """ """
        survival = load_survival_file(self.survival_tsv, path_data=self.path_data)
        matrix = []

        for sample in self.sample_ids:
            try:
                assert(sample in survival)
            except AssertionError:
                raise Exception('sample: {0} not in survival!'.format(sample))

            matrix.append(survival[sample])

        self.survival = np.asmatrix(matrix)

    def load_survival_test(self):
        """ """
        survival = load_survival_file(self.survival_tsv_test, path_data=self.path_data)
        matrix = []

        for sample in self.sample_ids_test:
            try:
                assert(sample in survival)
            except AssertionError:
                raise Exception('sample: {0} not in survival!'.format(sample))

            matrix.append(survival[sample])

        self.survival_test = np.asmatrix(matrix)

    def normalize_training_array(self):
        """ """
        for key in self.matrix_array:
            matrix = self.matrix_array[key]
            matrix = self._normalize(matrix, key)
            self.matrix_array_train[key] = matrix

    def _normalize(self,
                   matrix,
                   key,
                   mad_scale=TRAIN_MAD_SCALE,
                   robust_scale=TRAIN_ROBUST_SCALE,
                   min_max=TRAIN_MIN_MAX,
                   norm_scale=TRAIN_NORM_SCALE,
                   rank_scale=TRAIN_RANK_NORM,
                   corr_rank_scale=TRAIN_CORR_RANK_NORM,
                   dim_reduction=TRAIN_CORR_REDUCTION):
        """ """
        print('normalizing for {0}...'.format(key))

        if mad_scale:
            matrix = self.mad_scaler.fit_transform(matrix.T).T

        if robust_scale:
            matrix = self.robust_scaler.fit_transform(matrix)

        if min_max:
            matrix = MinMaxScaler().fit_transform(
                matrix.T).T

        if rank_scale:
            matrix = RankNorm().fit_transform(
                matrix)

        if dim_reduction:
            print('dim reduction for {0}...'.format(key))
            reducer = CorrelationReducer()
            matrix = reducer.fit_transform(
                matrix)

            if corr_rank_scale:
                matrix = RankNorm().fit_transform(
                    matrix)

        if norm_scale:
            matrix = self.normalizer.fit_transform(
                matrix)

        return matrix

    def transform_matrices(self,
                           matrix_ref, matrix, key,
                           mad_scale=TRAIN_MAD_SCALE,
                           robust_scale=TRAIN_ROBUST_SCALE,
                           min_max_scale=TRAIN_MIN_MAX,
                           rank_scale=TRAIN_RANK_NORM,
                           correlation_reducer=TRAIN_CORR_REDUCTION,
                           corr_rank_scale=TRAIN_CORR_RANK_NORM,
                           unit_norm=TRAIN_NORM_SCALE):
        """ """
        print('Scaling/Normalising dataset...')
        if min_max_scale:
            matrix_ref = self.min_max_scaler.fit_transform(matrix_ref.T).T
            matrix = self.min_max_scaler.fit_transform(matrix.T).T

        if rank_scale and not min_max_scale:
            matrix_ref = RankNorm().fit_transform(matrix_ref)
            matrix = RankNorm().fit_transform(matrix)

        if mad_scale:
            matrix_ref = self.mad_scaler.fit_transform(matrix_ref.T).T
            matrix = self.mad_scaler.fit_transform(matrix.T).T

        if robust_scale:
            matrix_ref = self.robust_scaler.fit_transform(matrix_ref)
            matrix = self.robust_scaler.transform(matrix)

        if correlation_reducer:
            reducer = CorrelationReducer()
            matrix_ref = reducer.fit_transform(matrix_ref)
            matrix = reducer.transform(matrix)

            self.feature_test_array[key] = self.sample_ids
            self.feature_ref_array[key] = self.sample_ids

            if corr_rank_scale:
                matrix_ref = RankNorm().fit_transform(matrix_ref)
                matrix = RankNorm().fit_transform(matrix)

        if unit_norm:
            matrix_ref = self.normalizer.fit_transform(matrix_ref)
            matrix = self.normalizer.transform(matrix)

        return matrix_ref, matrix


if __name__ == '__main__':
    main()
