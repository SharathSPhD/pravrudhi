"""Shared enums. Sanskrit primary keys are the identifiers; the wire value is the IAST-stripped ASCII form."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CandidateId = Annotated[str, StringConstraints(pattern=r"^c-\d{4,}$")]


class Pramana(StrEnum):
    """Provenance tag on every stored claim (wire key: provenance)."""

    pratyaksha = "pratyaksha"  # kernel-executed measurement
    anumana = "anumana"  # surrogate / posterior inference, sensor read
    upamana = "upamana"  # transfer analogy from another model or task
    agama = "agama"  # LLM testimony; every proposal at birth


class Surface(StrEnum):
    H1_guard = "H1.guard"
    H2_context = "H2.context"
    H3_prompt = "H3.prompt"
    H4_playbook = "H4.playbook"
    H5_skill = "H5.skill"
    H6_knob = "H6.knob"
    H7_acq = "H7.acq"
    W1_steer = "W1.steer"
    W2_data = "W2.data"
    W3_adapter = "W3.adapter"
    I1_sensor = "I1.sensor"
    T0_kernel = "T0.kernel"  # exists only so a candidate naming it can be refused


class Stage(StrEnum):
    smoke = "smoke"
    screen = "screen"
    confirm = "confirm"


Tier = Stage


class MeasureClass(StrEnum):
    na = "n/a"
    exploratory = "exploratory"
    pipeline_measured = "pipeline-measured"
    model_measured = "model-measured"


class Hetvabhasa(StrEnum):
    savyabhicara = "savyabhicara"  # inconsistent
    viruddha = "viruddha"  # contradictory
    asiddha = "asiddha"  # unestablished
    satpratipaksa = "satpratipaksa"  # counterbalanced
    badhita = "badhita"  # defeated by stronger evidence


class Isolation(StrEnum):
    process = "process"
    container = "container"
    user = "user"


class Residency(StrEnum):
    reasoner = "reasoner"
    executor = "executor"
    either = "either"


class AbstractionLevel(StrEnum):
    para = "para"  # intent
    pasyanti = "pasyanti"  # plan
    madhyama = "madhyama"  # code / diff
    vaikhari = "vaikhari"  # run


class EventKind(StrEnum):
    propose = "propose"
    predict = "predict"
    select = "select"
    spend = "spend"
    observe = "observe"
    skip = "skip"
    promote = "promote"
    prune = "prune"
    sublate = "sublate"
    audit = "audit"
    reflect = "reflect"
    signoff = "signoff"
    sensor = "sensor"


class KernelModel(BaseModel):
    """Base for every kernel schema type: unknown keys rejected, immutable, enum values on the wire."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class Bucket(KernelModel):
    task_family: str
    target_model: str
    corpus: str
