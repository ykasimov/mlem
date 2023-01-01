from typing import Any, ClassVar, Iterator, Tuple

import scipy
from scipy import sparse
from scipy.sparse import spmatrix

from mlem.core.artifacts import Artifacts, Storage
from mlem.core.data_type import (
    DataHook,
    DataReader,
    DataType,
    DataWriter,
    WithDefaultSerializer,
)
from mlem.core.hooks import IsInstanceHookMixin
from mlem.core.requirements import InstallableRequirement, Requirements


class ScipySparseMatrix(
    WithDefaultSerializer, DataType, DataHook, IsInstanceHookMixin
):
    type: ClassVar[str] = "csr_matrix"
    valid_types: ClassVar = (spmatrix,)
    dtype: str

    def get_requirements(self) -> Requirements:
        return Requirements.new([InstallableRequirement.from_module(scipy)])

    @classmethod
    def process(cls, obj: Any, **kwargs) -> DataType:
        return ScipySparseMatrix(dtype=obj.dtype.name)

    def get_writer(
        self, project: str = None, filename: str = None, **kwargs
    ) -> DataWriter:
        return ScipyWriter(**kwargs)


class ScipyWriter(DataWriter[ScipySparseMatrix]):
    def write(
        self, data: DataType, storage: Storage, path: str
    ) -> Tuple[DataReader, Artifacts]:
        with storage.open(path) as (f, art):
            sparse.save_npz(f, data.data)
        return ScipyReader(data_type=data), {self.art_name: art}


class ScipyReader(DataReader):
    type: ClassVar[str] = "csr_matrix"

    def read_batch(
        self, artifacts: Artifacts, batch_size: int
    ) -> Iterator[DataType]:
        raise NotImplementedError

    def read(self, artifacts: Artifacts) -> Iterator[DataType]:
        if DataWriter.art_name not in artifacts:
            raise ValueError(
                f"Wrong artifacts {artifacts}: should be one {DataWriter.art_name} file"
            )
        with artifacts[DataWriter.art_name].open() as f:
            data = sparse.load_npz(f)
        return self.data_type.copy().bind(data)
