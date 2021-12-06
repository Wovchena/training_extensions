import itertools
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type

from .training_test_case import (OTETestCaseInterface,
                                    generate_ote_integration_test_case_class)
from .training_tests_actions import get_default_test_action_classes
from .training_tests_common import DEFAULT_FIELD_VALUE_FOR_USING_IN_TEST

logger = logging.getLogger(__name__)


class OTETrainingTestInterface(ABC):
    """
    The interface for all OTE training tests
    (both reallife training tests and integration training tests)
    """
    @classmethod
    @abstractmethod
    def get_list_of_tests(cls, usecase: Optional[str] = None):
        raise NotImplementedError('The method is not implemented')

class OTETestCreationParametersInterface(ABC):
    """
    The interface for classes that gives parameters for creating
    OTE training tests.
    It is used as the input value for OTETestHelper class that
    makes most part of functionality for the training tests.
    """
    @abstractmethod
    def test_bunches(self) -> List[Dict[str, Any]]:
        """
        The method should return test bunches struct.
        It should be a list of dicts, each dict contains info on one "test bunch",
        e.g.
            ```
            [
                dict(
                    model_name=[
                       'gen3_mobilenetV2_SSD',
                       'gen3_mobilenetV2_ATSS',
                       'gen3_resnet50_VFNet',
                    ],
                    dataset_name='dataset1_tiled_shortened_500_A',
                    usecase='precommit',
                ),
                ...
            ]
            ```
        Note that the dict-s are passed to the tests as is through the parameter 'test_parameters'
        -- see the method OTETestHelper.get_list_of_tests below and the fixture
        fixtures.current_test_parameters_fx.
        """
        raise NotImplementedError('The method is not implemented')

    @abstractmethod
    def test_case_class(self) -> Type[OTETestCaseInterface]:
        """
        The method returns a class that will be used as a Test Case class
        for training tests.
        Note that it should return a class itself (not an instance of the class).

        Typically OTE Test Case class should be generated by the function
        training_test_case.generate_ote_integration_test_case_class.

        Note that the function receives as the parameter the list of action
        classes -- see the function
        training_tests_actions.get_default_test_action_classes,
        it returns the default test action classes.
        """
        raise NotImplementedError('The method is not implemented')

    @abstractmethod
    def short_test_parameters_names_for_generating_id(self) -> OrderedDict:
        """
        The method returns an OrderedDict that is used for generating string id-s of tests
        by test parameters, received from test bunches dicts:
        * keys of the OrderedDict should be the string keys of test bunches dict-s that should be
          used for generating id-s
        * values of the OrderedDict should be the strings that will be used as names of test parameters

        See the function OTETestHelper._generate_test_id below.
        """
        raise NotImplementedError('The method is not implemented')

    @abstractmethod
    def test_parameters_defining_test_case_behavior(self) -> List[str]:
        """
        The method returns a list of strings -- names of the test parameters
        (i.e. keys of test bunches dicts) that define test case behavior.

        When several test cases are handled, if the next test has these parameters
        the same as for the previous test, the test case class is re-used for the next test.
        This allows re-using the result of previous test stages in the next test stages.
        """
        raise NotImplementedError('The method is not implemented')

    @abstractmethod
    def default_test_parameters(self) -> Dict[str, Any]:
        """
        The method returns a dict that points for test parameters
        the default values.

        If some dict in test bunches does not have a field that is pointed
        in the dict returned by default_test_parameters, the value for the field is
        set by the default value.
        """
        raise NotImplementedError('The method is not implemented')

class DefaultOTETestCreationParametersInterface(OTETestCreationParametersInterface):
    """
    The default implementation of some of the parameters for creation training tests.
    """
    def test_case_class(self) -> Type[OTETestCaseInterface]:
        return generate_ote_integration_test_case_class(get_default_test_action_classes())

    def short_test_parameters_names_for_generating_id(self) -> OrderedDict:
        DEFAULT_SHORT_TEST_PARAMETERS_NAMES_FOR_GENERATING_ID = OrderedDict([
                ('test_stage', 'ACTION'),
                ('model_name', 'model'),
                ('dataset_name', 'dataset'),
                ('num_training_iters', 'num_iters'),
                ('batch_size', 'batch'),
                ('usecase', 'usecase'),
        ])
        return deepcopy(DEFAULT_SHORT_TEST_PARAMETERS_NAMES_FOR_GENERATING_ID)

    def test_parameters_defining_test_case_behavior(self) -> List[str]:
        DEFAULT_TEST_PARAMETERS_DEFINING_IMPL_BEHAVIOR = ['model_name',
                                                          'dataset_name',
                                                          'num_training_iters',
                                                          'batch_size']
        return deepcopy(DEFAULT_TEST_PARAMETERS_DEFINING_IMPL_BEHAVIOR)

    def default_test_parameters(self) -> Dict[str, Any]:
        DEFAULT_TEST_PARAMETERS = {
                'num_iters': 1,
                'batch_size': 2,
        }
        return deepcopy(DEFAULT_TEST_PARAMETERS)

class OTETestHelper:
    """
    The main class helping creating OTE training tests.

    The instance of this class (with proper test_creation_parameters) should be
    created as a static field for the test class making training tests
    -- the class should be derived from the interface OTETrainingTestInterface
    and forward the call of the class method get_list_of_tests to the helper
    (see method get_list_of_tests below).

    The most important method of the class are
    * get_list_of_tests -- allows pytest trick generating test parameters for
                           the test class
    * get_test_case -- gets an instance of the test case class for the current test parameters,
                       allows re-using the instance between several tests.
    """
    class _Cache:
        def __init__(self):
            self._cache_parameters = {}
            self._cached_value = None
        def get(self):
            return self._cached_value
        def set(self, params, value):
            logger.debug(f'cache.set new value for parameters {params}')
            self._cache_parameters = deepcopy(params)
            self._cached_value = value
        def has_same_params(self, params):
            res = (self._cache_parameters == params)
            res_str = '==' if res else '!='
            logger.debug(f'cache.has_same_params: '
                         f'cache_parameters={self._cache_parameters} {res_str} {params}, res={res}')
            return res

    def __init__(self,
                 test_creation_parameters: OTETestCreationParametersInterface):
        assert isinstance(test_creation_parameters, OTETestCreationParametersInterface)

        self.test_case_class = test_creation_parameters.test_case_class()
        self.test_bunches = test_creation_parameters.test_bunches()

        self.short_test_parameters_names_for_generating_id = \
                test_creation_parameters.short_test_parameters_names_for_generating_id()
        #TODO(beynens): rename to test_parameters_defining_test_case
        self.test_parameters_defining_test_case_behavior = \
                test_creation_parameters.test_parameters_defining_test_case_behavior()
        self.default_test_parameters = \
                test_creation_parameters.default_test_parameters()

        self._cache = OTETestHelper._Cache()

        assert issubclass(self.test_case_class, OTETestCaseInterface)
        assert isinstance(self.short_test_parameters_names_for_generating_id, OrderedDict)
        assert all(isinstance(k, str) and isinstance(v, str)
                   for k, v in self.short_test_parameters_names_for_generating_id.items())
        assert 'test_stage' in self.short_test_parameters_names_for_generating_id
        assert 'model_name' in self.short_test_parameters_names_for_generating_id
        assert 'dataset_name' in self.short_test_parameters_names_for_generating_id
        assert 'usecase' in self.short_test_parameters_names_for_generating_id

        assert isinstance(self.test_parameters_defining_test_case_behavior, list)
        assert all(isinstance(s, str) for s in self.test_parameters_defining_test_case_behavior)

        assert isinstance(self.default_test_parameters, dict)
        assert all(isinstance(k, str) for k in self.default_test_parameters.keys())

    def _get_list_of_test_stages(self):
        return self.test_case_class.get_list_of_test_stages()

    def _fill_test_parameters_default_values(self, test_parameters):
        for key, default_val in self.default_test_parameters.items():
            val = test_parameters.get(key)
            if val is None or val == DEFAULT_FIELD_VALUE_FOR_USING_IN_TEST():
                test_parameters[key] = default_val

    def _generate_test_id(self, test_parameters):
        id_parts = (
                f'{short_par_name}-{test_parameters[par_name]}'
                for par_name, short_par_name in self.short_test_parameters_names_for_generating_id.items()
        )
        return ','.join(id_parts)

    def get_list_of_tests(self, usecase: Optional[str] = None):
        """
        The functions generates the lists of values for the tests from the field test_bunches of the class.

        The function returns two lists
        * argnames -- a tuple with names of the test parameters, at the moment it is
                      a one-element tuple with the parameter name "test_parameters"
        * argvalues -- list of tuples, each tuple has the same len as argname tuple,
                       at the moment it is a one-element tuple with the dict `test_parameters`
                       that stores the parameters of the test
        * ids -- list of strings with ids corresponding the parameters of the tests
                 each id is a string generated from the corresponding test_parameters
                 value -- see the functions _generate_test_id

        The lists argvalues and ids will have the same length.

        If the parameter `usecase` is set, it makes filtering by usecase field of test bunches.
        """
        test_bunches = self.test_bunches
        assert all(isinstance(el, dict) for el in test_bunches)

        argnames = ('test_parameters',)
        argvalues = []
        ids = []
        for el in test_bunches:
            el_model_name = el.get('model_name')
            el_dataset_name = el.get('dataset_name')
            el_usecase = el.get('usecase')
            if usecase is not None and el_usecase != usecase:
                continue
            if isinstance(el_model_name, (list, tuple)):
                model_names = el_model_name
            else:
                model_names = [el_model_name]
            if isinstance(el_dataset_name, (list, tuple)):
                dataset_names = el_dataset_name
            else:
                dataset_names = [el_dataset_name]

            model_dataset_pairs = list(itertools.product(model_names, dataset_names))

            for m, d in model_dataset_pairs:
                for test_stage in self._get_list_of_test_stages():
                    test_parameters = deepcopy(el)
                    test_parameters['test_stage'] = test_stage
                    test_parameters['model_name'] = m
                    test_parameters['dataset_name'] = d
                    self._fill_test_parameters_default_values(test_parameters)
                    argvalues.append((test_parameters,))
                    ids.append(self._generate_test_id(test_parameters))

        return argnames, argvalues, ids

    def get_test_case(self, test_parameters, params_factories_for_test_actions):
        """
        The method returns an instance of test case class for the current test parameters.
        If the main test parameters (pointed by the field test_parameters_defining_test_case_behavior)
        are the same as in the previous test, the instance of the test case is re-used from the previous test.
        It allows re-using results of previous tests stages in the next test stages.

        If a new instance of test case should be created, the method creates a class pointed
        by the field test_case_class. The parameter params_factories_for_test_actions is passed
        to the test case constructor
        (note that params_factories_for_test_actions are factories, not structs, to
        create the parameters only when this is required)
        """
        params_defining_cache = {k: test_parameters[k] for k in self.test_parameters_defining_test_case_behavior}
        if not self._cache.has_same_params(params_defining_cache):
            logger.info(f'OTETestHelper: parameters were changed -- updating cache')
            logger.info(f'OTETestHelper: before creating test case (class {self.test_case_class})')
            test_case = self.test_case_class(params_factories_for_test_actions)
            logger.info(f'OTETestHelper: after creating test case (class {self.test_case_class})')
            self._cache.set(params_defining_cache, test_case)
        else:
            logger.info('OTETestHelper: parameters were not changed -- cache is kept')

        return self._cache.get()
