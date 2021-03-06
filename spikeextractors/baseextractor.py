import json
import os
from pathlib import Path
import importlib
import numpy as np
import datetime
from copy import deepcopy
import tempfile
import pickle


class BaseExtractor:
    def __init__(self):
        self._kwargs = {}
        self._tmp_folder = None
        self._key_properties = {}
        self._properties = {}
        self._features = {}
        self.is_dumpable = True
        self.is_filtered = False

    def make_serialized_dict(self):
        '''
        Makes a nested serialized dictionary out of the extractor. The dictionary be used to re-initialize an
        extractor with spikeextractors.load_extractor_from_dict(dump_dict)

        Returns
        -------
        dump_dict: dict
            Serialized dictionary
        '''
        class_name = str(type(self)).replace("<class '", "").replace("'>", '')
        module = class_name.split('.')[0]
        imported_module = importlib.import_module(module)

        if self.is_dumpable:
            dump_dict = {'class': class_name, 'module': module, 'kwargs': self._kwargs,
                         'key_properties': self._key_properties, 'version': imported_module.__version__,
                         'dumpable': True}
        else:
            dump_dict = {'class': class_name, 'module': module, 'kwargs': {}, 'key_properties': self._key_properties,
                         'version': imported_module.__version__, 'dumpable': False}
        return dump_dict

    def dump_to_dict(self):
        '''
        Dumps recording to a dictionary.
        The dictionary be used to re-initialize an
        extractor with spikeextractors.load_extractor_from_dict(dump_dict)

        Returns
        -------
        dump_dict: dict
            Serialized dictionary
        '''
        return self.make_serialized_dict()

    def dump_to_json(self, file_path=None):
        '''
        Dumps recording extractor to json file.
        The extractor can be re-loaded with spikeextractors.load_extractor_from_json(json_file)

        Parameters
        ----------
        file_path: str
            Path of the json file
        '''
        if self.check_if_dumpable():
            if file_path is None:
                if 'Recording' in self.__class__:
                    file_path = 'spikeinterface_recording.json'
                elif 'Sorting' in self.__class__:
                    file_path = 'spikeinterface_sorting.json'
            file_path = Path(file_path)
            if not file_path.parent.is_dir():
                os.makedirs(str(file_path.parent))
            folder_path = file_path.parent
            if Path(file_path).suffix == '':
                file_path = folder_path / (str(file_path) + '.json')
            assert file_path.suffix == '.json', "'file_path' should be a .json file"
            dump_dict = self.make_serialized_dict()
            with open(str(file_path), 'w', encoding='utf8') as f:
                json.dump(_check_json(dump_dict), f, indent=4)
        else:
            raise Exception(f"The extractor is not dumpable to to json")

    def dump_to_pickle(self, file_path=None, include_properties=True, include_features=True):
        '''
        Dumps recording extractor to a pickle file.
        The extractor can be re-loaded with spikeextractors.load_extractor_from_json(json_file)

        Parameters
        ----------
        file_path: str
            Path of the json file
        include_properties: bool
            If True, all properties are dumped
        include_features: bool
            If True, all features are dumped
        '''
        if self.check_if_dumpable():
            dump_dict = {}
            if file_path is None:
                if 'Recording' in self.__class__:
                    file_path = 'spikeinterface_recording.pkl'
                elif 'Sorting' in self.__class__:
                    file_path = 'spikeinterface_sorting.pkl'
            file_path = Path(file_path)
            if not file_path.parent.is_dir():
                os.makedirs(str(file_path.parent))
            if Path(file_path).suffix == '':
                file_path = file_path.parent / (str(file_path) + '.pkl')
            assert file_path.suffix == '.pkl' or file_path.suffix == '.pickle', "'file_path' should be a .pkl or " \
                                                                                ".pickle file"

            # Dump all
            dump_dict['serialized_dict'] = self.make_serialized_dict()
            if include_properties:
                if len(self._properties.keys()) > 0:
                    dump_dict['properties'] = self._properties
            if include_features:
                if len(self._features.keys()) > 0:
                    dump_dict['features'] = self._features

            with file_path.open('wb') as f:
                pickle.dump(dump_dict, f)
        else:
            raise Exception(f"The extractor is not dumpable to to pkl")

    def get_tmp_folder(self):
        '''
        Returns temporary folder associated to the extractor

        Returns
        -------
        temp_folder: Path
            The temporary folder
        '''
        if self._tmp_folder is None:
            self._tmp_folder = Path(tempfile.mkdtemp())
        return self._tmp_folder

    def set_tmp_folder(self, folder):
        '''
        Sets temporary folder of the extractor

        Parameters
        ----------
        folder: str or Path
            The temporary folder
        '''
        self._tmp_folder = Path(folder)

    def allocate_array(self, memmap, shape=None, dtype=None, name=None, array=None):
        '''
        Allocates a memory or memmap array

        Parameters
        ----------
        memmap: bool
            If True, a memmap array is created in the sorting temporary folder
        shape: tuple
            Shape of the array. If None array must be given
        dtype: dtype
            Dtype of the array. If None array must be given
        name: str or None
            Name (root) of the file (if memmap is True). If None, a random name is generated
        array: np.array
            If array is given, shape and dtype are initialized based on the array. If memmap is True, the array is then
            deleted to clear memory

        Returns
        -------
        arr: np.array or np.memmap
            The allocated memory or memmap array
        '''
        if memmap:
            tmp_folder = self.get_tmp_folder()
            if array is not None:
                shape = array.shape
                dtype = array.dtype
            else:
                assert shape is not None and dtype is not None, "Pass 'shape' and 'dtype' arguments"
            if name is None:
                tmp_file = tempfile.NamedTemporaryFile(suffix=".raw", dir=tmp_folder).name
            else:
                if Path(name).suffix == '':
                    tmp_file = tmp_folder / (name + '.raw')
                else:
                    tmp_file = tmp_folder / name
            arr = np.memmap(tmp_file, mode='w+', shape=shape, dtype=dtype)
            if array is not None:
                arr[:] = array
                del array
            else:
                arr[:] = 0
        else:
            if array is not None:
                arr = array
            else:
                arr = np.zeros(shape, dtype=dtype)
        return arr

    def _cast_start_end_frame(self, start_frame, end_frame):
        from .extraction_tools import cast_start_end_frame
        return cast_start_end_frame(start_frame, end_frame)


    @staticmethod
    def load_extractor_from_json(json_file):
        '''
        Instantiates extractor from json file

        Parameters
        ----------
        json_file: str or Path
            Path to json file

        Returns
        -------
        extractor: RecordingExtractor or SortingExtractor
            The loaded extractor object
        '''
        json_file = Path(json_file)
        with open(str(json_file), 'r') as f:
            d = json.load(f)
            extractor = _load_extractor_from_dict(d)
        return extractor

    @staticmethod
    def load_extractor_from_pickle(pkl_file):
        '''
        Instantiates extractor from json file

        Parameters
        ----------
        json_file: str or Path
            Path to json file

        Returns
        -------
        extractor: RecordingExtractor or SortingExtractor
            The loaded extractor object
        '''
        pkl_file = Path(pkl_file)
        with open(str(pkl_file), 'rb') as f:
            d = pickle.load(f)
        extractor = _load_extractor_from_dict(d['serialized_dict'])
        if 'properties' in d.keys():
            extractor._properties = d['properties']
        if 'features' in d.keys():
            extractor._features = d['features']
        return extractor

    @staticmethod
    def load_extractor_from_dict(d):
        '''
        Instantiates extractor from dictionary

        Parameters
        ----------
        d: dictionary
            Python dictionary

        Returns
        -------
        extractor: RecordingExtractor or SortingExtractor
            The loaded extractor object
        '''
        extractor = _load_extractor_from_dict(d)
        return extractor

    def check_if_dumpable(self):
        return _check_if_dumpable(self.make_serialized_dict())


def _load_extractor_from_dict(dic):
    cls = None
    class_name = None
    probe_file = None
    kwargs = deepcopy(dic['kwargs'])
    if np.any([isinstance(v, dict) for v in kwargs.values()]):
        # nested
        for k in kwargs.keys():
            if isinstance(kwargs[k], dict):
                if 'module' in kwargs[k].keys() and 'class' in kwargs[k].keys() and 'version' in kwargs[k].keys():
                    extractor = _load_extractor_from_dict(kwargs[k])
                    class_name = dic['class']
                    cls = _get_class_from_string(class_name)
                    kwargs[k] = extractor
                    break
    elif np.any([isinstance(v, list) and isinstance(v[0], dict) for v in kwargs.values()]):
        # multi
        for k in kwargs.keys():
            if isinstance(kwargs[k], list) and isinstance(kwargs[k][0], dict):
                extractors = []
                for kw in kwargs[k]:
                    if 'module' in kw.keys() and 'class' in kw.keys() and 'version' in kw.keys():
                        extr = _load_extractor_from_dict(kw)
                        extractors.append(extr)
                class_name = dic['class']
                cls = _get_class_from_string(class_name)
                kwargs[k] = extractors
                break
    else:
        class_name = dic['class']
        cls = _get_class_from_string(class_name)

    assert cls is not None and class_name is not None, "Could not load spikeinterface class"
    if not _check_same_version(class_name, dic['version']):
        print('Versions are not the same. This might lead to errors. Use ', class_name.split('.')[0],
              'version', dic['version'])

    if 'probe_file' in kwargs.keys():
        probe_file = kwargs.pop('probe_file')

    # instantiate extrator object
    extractor = cls(**kwargs)

    # load probe file
    if probe_file is not None:
        assert 'Recording' in class_name, "Only recording extractors can have probe files"
        extractor = extractor.load_probe_file(probe_file=probe_file)

    # load properties and features
    if 'key_properties' in dic.keys():
        extractor._key_properties = dic['key_properties']

    return extractor


def _get_class_from_string(class_string):
    class_name = class_string.split('.')[-1]
    module = '.'.join(class_string.split('.')[:-1])
    imported_module = importlib.import_module(module)

    try:
        imported_class = getattr(imported_module, class_name)
    except:
        imported_class = None

    return imported_class


def _check_same_version(class_string, version):
    module = class_string.split('.')[0]
    imported_module = importlib.import_module(module)

    return imported_module.__version__ == version


def _check_if_dumpable(d):
    kwargs = d['kwargs']
    if np.any([isinstance(v, dict) and 'dumpable' in v.keys() for (k, v) in kwargs.items()]):
        for k, v in kwargs.items():
            if 'dumpable' in v.keys():
                return _check_if_dumpable(v)
    else:
        return d['dumpable']


def _check_json(d):
    # quick hack to ensure json writable
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = _check_json(v)
        elif isinstance(v, Path):
            d[k] = str(v.absolute())
        elif isinstance(v, bool):
            d[k] = bool(v)
        elif isinstance(v, (np.int, np.int32, np.int64)):
            d[k] = int(v)
        elif isinstance(v, (np.float, np.float32, np.float64)):
            d[k] = float(v)
        elif isinstance(v, datetime.datetime):
            d[k] = v.isoformat()
        elif isinstance(v, (np.ndarray, list)):
            if len(v) > 0:
                if isinstance(v[0], dict):
                    # these must be extractors for multi extractors
                    d[k] = [_check_json(v_el) for v_el in v]
                else:
                    v_arr = np.array(v)
                    if len(v_arr.shape) == 1:
                        if 'int' in str(v_arr.dtype):
                            v_arr = [int(v_el) for v_el in v_arr]
                            d[k] = v_arr
                        elif 'float' in str(v_arr.dtype):
                            v_arr = [float(v_el) for v_el in v_arr]
                            d[k] = v_arr
                        else:
                            print('Skipping field: only int or float can be serialized')
                    elif len(v_arr.shape) == 2:
                        if 'int' in str(v_arr.dtype):
                            v_arr = [[int(v_el) for v_el in v_row] for v_row in v_arr]
                            d[k] = v_arr
                        elif 'float' in str(v_arr.dtype):
                            v_arr = [[float(v_el) for v_el in v_row] for v_row in v_arr]
                            d[k] = v_arr
                        else:
                            print('Skipping field: only int or float can be serialized')
                    else:
                        print("Skipping field: only 1D and 2D arrays can be serialized")
            else:
                d[k] = list(v)
    return d