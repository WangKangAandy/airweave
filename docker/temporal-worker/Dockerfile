FROM airweave-backend-local:local

WORKDIR /app

# Preinstall worker runtime dependencies so startup does not rely on network.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir sentence-transformers model2vec

# Bake semantic chunker local model into image for offline startup.
COPY docker/temporal-worker/assets/potion-base-32M /model_files

ENV HF_HOME=/root/.cache/huggingface \
    HF_HUB_LOCAL_FILES_ONLY=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
