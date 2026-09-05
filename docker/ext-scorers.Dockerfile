# External scorers image: lm-evaluation-harness and EvalPlus on top of the execution image. Built with network;
# run without it. lm-eval 0.4.x needs transformers 4.x, so this image carries its own transformers; it only scores.
FROM pravrudhi/exec-5090:latest
RUN pip install --no-cache-dir "transformers<5" "lm-eval[hf]==0.4.9" "evalplus>=0.3.1" 2>&1 | tail -2
ENTRYPOINT []
CMD ["bash"]
