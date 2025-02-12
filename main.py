import os
import json
import time
import base64
import openai
from tqdm import tqdm
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 生成并保存加密密钥
if not os.path.exists('fernet.key'):
    with open('fernet.key', 'wb') as key_file:
        key = Fernet.generate_key()
        key_file.write(key)

with open('fernet.key', 'rb') as key_file:
    key = key_file.read()

cipher_suite = Fernet(key)

def encrypt_api_key(api_key):
    # 确保API key是字符串
    if not isinstance(api_key, str):
        api_key = str(api_key)
    # 加密并返回base64编码的字符串
    encrypted = cipher_suite.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_api_key(encrypted_key):
    # 确保base64字符串长度是4的倍数
    padding = len(encrypted_key) % 4
    if padding:
        encrypted_key += '=' * (4 - padding)
    # 解码base64字符串
    encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
    # 解密并返回原始字符串
    return cipher_suite.decrypt(encrypted).decode()

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

def save_api_keys(config, api_keys):
    with open('.env', 'w') as f:
        for endpoint, api_key in zip(config, api_keys):
            name = endpoint['name'].replace(' ', '_').upper()
            f.write(f"{name}_API_KEY={api_key}\n")

def load_api_keys(config):
    api_keys = {}
    if not os.path.exists('.env'):
        return None
    with open('.env', 'r') as f:
        for line in f:
            if line.strip() and '=' in line:
                key, value = line.strip().split('=', 1)
                api_keys[key] = value
    return api_keys if api_keys else None

def test_endpoint(endpoint, api_keys):
    name = endpoint['name'].replace(' ', '_').upper()
    api_key = api_keys.get(f"{name}_API_KEY")
    if not api_key:
        print(f"找不到 {endpoint['name']} 的 API key")
        return None
        
    client = openai.OpenAI(
        api_key=decrypt_api_key(api_key),
        base_url=endpoint['url']
    )
    start_time = time.time()
    try:
        with open('speed_test_prompt.txt', 'r', encoding='utf-8') as f:
            prompt = f.readlines()[0].split(": ")[1].strip('"')
        
        response = client.chat.completions.create(
            model=endpoint.get("model", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        return time.time() - start_time, response.choices[0].message.content
    except Exception as e:
        return -1, str(e)

def main():
    # 检查并创建配置文件
    if not os.path.exists('config.json'):
        with open('config.json', 'w') as f:
            json.dump([], f)

    # 加载并验证配置
    config = load_config()
    if not isinstance(config, list):
        print("配置文件格式错误，应为列表")
        return

    # 检查API keys
    api_keys = load_api_keys(config)
    if api_keys is None:
        api_keys = {}
        for endpoint in config:
            while True:
                api_key = input(f"请输入 {endpoint['name']} 的 API key: ").strip()
                if api_key.startswith('sk-') and len(api_key) > 30:
                    try:
                        # 先加密再保存
                        encrypted_key = encrypt_api_key(api_key)
                        name = endpoint['name'].replace(' ', '_').upper()
                        api_keys[f"{name}_API_KEY"] = encrypted_key
                        break
                    except Exception as e:
                        print(f"加密API key时出错: {str(e)}")
                        continue
                else:
                    print("无效的API key格式，应以'sk-'开头且长度大于30")
        save_api_keys(config, list(api_keys.values()))

    # 测试所有端点
    results = []
    for endpoint in tqdm(config, desc="Testing endpoints"):
        result = test_endpoint(endpoint, api_keys)
        if result is not None:
            latency, response = result
            results.append({
                'name': endpoint['name'],
                'latency': latency,
                'response': response
            })

    # 显示结果
    print("\nLatency Results:")
    for result in results:
        print(f"{result['name']}: {result['latency']:.2f}s")
        print(f"Response: {result['response']}\n")

if __name__ == "__main__":
    main()