# API 延迟测试工具

本项目是一个基于 OpenAI 库的 API 连通性测试工具，用于测试多个 API 端点的响应时间和正确性。通过配置文件定义要测试的 API 端点，并自动加密存储 API 密钥。

## 配置文件说明

配置文件 `config.toml` 使用 TOML 格式，包含多个 API 端点的配置。每个端点需要定义以下字段：

- `name`: 端点名称
- `url`: API 的 URL 地址
- `model`: 使用的模型名称
- `api_key`: API 密钥（可选，首次配置后会被加密存储）

示例配置：

```toml
[[endpoints]]
name = "deepseek v3 official"
url = "https://api.deepseek.com"
model = "deepseek-chat"
api_key = "your_api_key_here"
```

## 使用方法

1. 确保已安装 Python 3.x 和所需依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 编辑 `config.toml` 文件，添加要测试的 API 端点配置。

3. 运行测试：
   ```bash
   python main.py
   ```

4. 如果某个端点缺少 API 密钥，程序会提示输入并自动加密存储。

## 输出结果

测试完成后，程序会输出每个端点的响应时间和测试结果。示例输出：

```
Latency Results:
deepseek v3 official: 1.23s
Response: 我是 DeepSeek Chat，版本 3.0
```

## 注意事项

- API 密钥会被加密存储在 `.api_keys.enc` 文件中，请勿手动修改该文件。
- 测试使用的提示词可以在 `speed_test_prompt.txt` 中修改。