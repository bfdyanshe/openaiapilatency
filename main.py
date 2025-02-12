import os
import toml
import time
import base64
import openai
import asyncio
from tqdm.asyncio import tqdm as async_tqdm
from cryptography.fernet import Fernet


class ConfigManager:
    @staticmethod
    def load_config():
        config = toml.load("config.toml")
        return {
            "endpoints": config.get("endpoints", []),
            "test_config": config.get(
                "test_config", {"max_total_time": 20, "max_requests": 3}
            ),
        }

    @staticmethod
    def save_config(config):
        with open("config.toml", "w") as f:
            toml.dump(config, f)


class APIKeyManager:
    def __init__(self):
        self.cipher_suite = self._init_cipher()

    def _init_cipher(self):
        if not os.path.exists("fernet.key"):
            with open("fernet.key", "wb") as key_file:
                key = Fernet.generate_key()
                key_file.write(key)

        with open("fernet.key", "rb") as key_file:
            return Fernet(key_file.read())

    def encrypt(self, api_key):
        if not isinstance(api_key, str):
            api_key = str(api_key)
        encrypted = self.cipher_suite.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_key):
        padding = len(encrypted_key) % 4
        if padding:
            encrypted_key += "=" * (4 - padding)
        encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
        return self.cipher_suite.decrypt(encrypted).decode()


class APIKeyStorage:
    @staticmethod
    def load_keys():
        if not os.path.exists(".api_keys.enc"):
            return {}

        with open(".api_keys.enc", "r") as f:
            return dict(
                line.strip().split("=", 1) for line in f if line.strip() and "=" in line
            )

    @staticmethod
    def save_keys(keys):
        with open(".api_keys.enc", "w") as f:
            for key, value in keys.items():
                f.write(f"{key}={value}\n")


async def test_endpoint(
    endpoint, api_keys, key_manager, prompt, max_total_time=20, max_requests=3
):
    name = endpoint["name"].replace(" ", "_").upper()
    api_key = api_keys.get(f"{name}_API_KEY")
    if not api_key:
        return -1, f"找不到 {endpoint['name']} 的 API key"

    client = openai.AsyncOpenAI(
        api_key=key_manager.decrypt(api_key), base_url=endpoint["url"]
    )

    total_time = 0
    total_requests = 0
    successful_requests = 0
    errors = []
    last_response = None
    total_ttft = 0
    first_token = ""

    while total_time < max_total_time and total_requests < max_requests:
        start_time = time.time()
        try:
            first_token_time = None
            ttft_info = ""
            last_response = ""
            stream = await client.chat.completions.create(
                model=endpoint.get("model", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0,
                timeout=60,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices[0].delta.content:
                    continue
                if not first_token_time:
                    first_token_time = time.time() - start_time
                    first_token = chunk.choices[0].delta.content
                last_response += chunk.choices[0].delta.content
            latency = time.time() - start_time
            total_time += latency
            total_requests += 1
            successful_requests += 1
            if first_token_time:
                total_ttft += first_token_time
        except Exception as e:
            latency = time.time() - start_time
            total_time += latency
            total_requests += 1
            errors.append(str(e))
            break

    if successful_requests == 0:
        return -1, f"所有请求均失败：{', '.join(errors)}; 总耗时：{total_time}"

    avg_latency = total_time / total_requests if total_requests > 0 else 0
    ttft_info = (
        "" if total_ttft == 0 else f"，平均 ttft: {total_ttft/successful_requests:.2f}s"
    )
    if errors:
        return (
            total_time,
            f"部分请求成功：{successful_requests}/{total_requests}，平均耗时：{avg_latency:.2f}s {ttft_info}，最后一次响应：{last_response}，错误：{', '.join(errors)}",
        )
    return (
        total_time,
        f"所有请求成功：{successful_requests}/{total_requests}，平均耗时：{avg_latency:.2f}s {ttft_info}，最后一次响应：{last_response}",
    )


async def main():
    if not os.path.exists("config.toml"):
        ConfigManager.save_config({"test_config": {}, "endpoints": [{}]})

    config = ConfigManager.load_config()
    endpoints = config["endpoints"]
    test_config = config["test_config"]

    if not isinstance(endpoints, list):
        print("配置文件格式错误，endpoints 应为列表")
        return

    key_manager = APIKeyManager()
    api_keys = APIKeyStorage.load_keys()

    # 处理API keys
    for endpoint in endpoints:
        name = endpoint["name"].replace(" ", "_").upper()
        key_name = f"{name}_API_KEY"
        if "api_key" in endpoint:
            # 优先使用config中的api_key
            api_key = endpoint["api_key"]
            try:
                encrypted_key = key_manager.encrypt(api_key)
                api_keys[key_name] = encrypted_key
                APIKeyStorage.save_keys(api_keys)
                del endpoint["api_key"]  # 删除config中的api_key
                ConfigManager.save_config(
                    {
                        "test_config": test_config,
                        "endpoints": endpoints,
                    }
                )
            except Exception as e:
                print(f"加密API key时出错: {str(e)}")

        # 如果api_keys文件中没有，则提示用户输入
        if key_name not in api_keys:
            api_key = (
                input(f"找不到 {endpoint['name']} 的 API key，是否要添加？(y/n): ")
                .strip()
                .lower()
            )
            if api_key == "y":
                while True:
                    api_key = input(f"请输入 {endpoint['name']} 的 API key: ").strip()
                    if api_key.startswith("sk") and len(api_key) > 30:
                        try:
                            encrypted_key = key_manager.encrypt(api_key)
                            api_keys[key_name] = encrypted_key
                            APIKeyStorage.save_keys(api_keys)
                            break
                        except Exception as e:
                            print(f"加密API key时出错: {str(e)}")
                    else:
                        print("无效的 API key 格式，应以 'sk' 开头且长度大于 30")

    # 读取 prompt
    with open("speed_test_prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.readlines()[0].split(": ")[1].strip('"')

    # 测试所有端点
    tasks = [
        test_endpoint(
            endpoint,
            api_keys,
            key_manager,
            prompt,
            test_config["max_total_time"],
            test_config["max_requests"],
        )
        for endpoint in endpoints
    ]
    results = await async_tqdm.gather(*tasks, desc="Testing endpoints")

    # 显示结果
    print("\nLatency Results:")
    for endpoint, result in zip(endpoints, results):
        latency, response = result
        print(f"{endpoint['name']}: {latency:.2f}s")
        print(f"{'Response' if latency != -1 else 'Error'}: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
