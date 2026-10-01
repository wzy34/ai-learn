# 微信云托管部署文件
# 平台要求：
#   - 容器监听 0.0.0.0，端口以版本配置「监听端口」为准（平台注入 PORT 环境变量，默认 80）
#   - 日志打印到 stdout/stderr 即可被日志采集（采集路径留空时默认采集标准输出）

FROM python:3.12-slim

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先复制依赖清单再安装，利用构建缓存：依赖不变时后续构建直接命中缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 仅复制运行所需内容，.env / venv / tests 不会进入镜像
COPY app ./app
COPY sql ./sql

# 头像上传目录（app/main.py 启动时也会自动创建），预创建并授权给非 root 用户
RUN mkdir -p /app/uploads/avatars \
    && useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

# 与云托管默认「监听端口 80」一致；运行时以注入的 PORT 环境变量优先
EXPOSE 80

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-80}"]
