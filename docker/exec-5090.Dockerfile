# Pravrudhi execution image for the RTX 5090 (ADR-0003): derived from the NVIDIA PyTorch 25.06 lineage that is
# present and working on this host (torch 2.8+cu12.9, SM120, transformers 5.13, PEFT, TRL, bitsandbytes).
# The blueprint's torch 2.10 + cu130 + Unsloth stack is the P1 target; every figure about this image is measured
# by `pravrudhi preflight`, never quoted. Build: make exec-image
FROM rtx5090-train:latest
LABEL org.pravrudhi.lineage="nvcr.io/nvidia/pytorch:25.06-py3 -> rtx5090-train:latest"
# PEFT 0.19 refuses the lineage's torchao 0.11 (needs >=0.16); nothing here uses torchao, so remove it.
RUN pip uninstall -y torchao >/dev/null 2>&1 || true
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME=/models PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false
COPY docker/jobs /opt/pravrudhi/jobs
WORKDIR /work
ENV PYTHONPATH=/opt/pravrudhi/jobs
# Job is selected by the first argument: generate | sample | train_sft | train_grpo | anchor_nll
COPY docker/entry.sh /opt/pravrudhi/entry.sh
ENTRYPOINT ["bash", "/opt/pravrudhi/entry.sh"]
