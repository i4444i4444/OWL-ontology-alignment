import inspect
from ontoaligner.aligner import (
    TFIDFRetrieval,
    BM25Retrieval,
    SBERTRetrieval,
)

classes = [
    TFIDFRetrieval,
    BM25Retrieval,
    SBERTRetrieval,
]

for cls in classes:
    print("\n" + "=" * 60)
    print("CLASS:", cls.__name__)

    print("\nConstructor:")
    print(inspect.signature(cls))

    print("\nInitialization source:")
    print(inspect.getsource(cls.__init__))

    print("\nGenerate source:")
    print(inspect.getsource(cls.generate))