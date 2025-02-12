<script>
  import { onMount } from 'svelte';
  import { ConfigManager } from '$lib/config';
  import { APIKeyManager, APIKeyStorage } from '$lib/storage';
  import { APITester } from '$lib/api';

  /** @type {import('$lib/config').Endpoint[]} */
  let endpoints = [];
  
  /** @type {Array<{name: string, latency: number, result: string}>} */
  let testResults = [];
  
  let isLoading = false;
  
  /** @type {string | null} */
  let error = null;

  onMount(async () => {
    const config = await ConfigManager.loadConfig();
    endpoints = config.endpoints;
  });

  async function testAllEndpoints() {
    if (endpoints.length === 0) {
      error = '请先添加至少一个端点';
      return;
    }

    isLoading = true;
    error = null;
    testResults = [];

    try {
      const config = await ConfigManager.loadConfig();
      const prompt = '你好，请介绍一下你自己';

      for (const endpoint of endpoints) {
        try {
          const [latency, result] = await APITester.testEndpoint(
            endpoint,
            prompt,
            config.testConfig.maxTotalTime,
            config.testConfig.maxRequests
          );
          testResults.push({ name: endpoint.name, latency, result });
        } catch (e) {
          testResults.push({
            name: endpoint.name,
            latency: -1,
            result: e instanceof Error ? e.message : String(e)
          });
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      isLoading = false;
    }
  }

  let showAddForm = false;
  let newEndpoint = {
    name: '',
    url: '',
    model: '',
    apiKey: ''
  };

  async function addEndpoint() {
    if (!newEndpoint.name || !newEndpoint.url || !newEndpoint.model || !newEndpoint.apiKey) {
      error = '请填写所有字段';
      return;
    }

    try {
      const encryptedKey = await APIKeyManager.encrypt(newEndpoint.apiKey);
      const endpoint = { ...newEndpoint, apiKey: encryptedKey };

      const config = await ConfigManager.loadConfig();
      endpoints = [...endpoints, endpoint];
      await ConfigManager.saveConfig({ ...config, endpoints });
      APIKeyStorage.saveKeys({ [`${newEndpoint.name}_API_KEY`]: encryptedKey });

      // 重置表单
      newEndpoint = {
        name: '',
        url: '',
        model: '',
        apiKey: ''
      };
      showAddForm = false;
      error = null;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
</script>

<style>
  .container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }

  .endpoint-list {
    margin-bottom: 20px;
  }

  .endpoint-item {
    padding: 10px;
    border: 1px solid #ddd;
    margin-bottom: 10px;
    border-radius: 4px;
  }

  .test-results {
    margin-top: 20px;
  }

  .result-item {
    padding: 10px;
    border: 1px solid #ddd;
    margin-bottom: 10px;
    border-radius: 4px;
  }

  .error {
    color: red;
    margin-top: 10px;
    padding: 10px;
    background-color: #ffeeee;
    border: 1px solid #ffcccc;
    border-radius: 4px;
  }

  button {
    margin-right: 10px;
    padding: 8px 16px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  button:hover {
    background-color: #0056b3;
  }

  button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  .add-form {
    margin-top: 20px;
    padding: 20px;
    background-color: #f5f5f5;
    border-radius: 8px;
  }

  .form-group {
    margin-bottom: 15px;
  }

  .form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
  }

  .form-group input {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    box-sizing: border-box;
  }
</style>

<main class="container">
  <h1>API 延迟测试</h1>

  <div class="endpoint-list">
    {#each endpoints as endpoint}
      <div class="endpoint-item">
        <h3>{endpoint.name}</h3>
        <p>URL: {endpoint.url}</p>
        <p>Model: {endpoint.model}</p>
      </div>
    {/each}
  </div>

  <button on:click={() => showAddForm = !showAddForm} disabled={isLoading}>
    {showAddForm ? '取消添加' : '添加端点'}
  </button>

  {#if showAddForm}
    <div class="add-form">
      <h3>添加新端点</h3>
      <div class="form-group">
        <label for="name">名称:</label>
        <input id="name" type="text" bind:value={newEndpoint.name} />
      </div>
      <div class="form-group">
        <label for="url">URL:</label>
        <input id="url" type="text" bind:value={newEndpoint.url} />
      </div>
      <div class="form-group">
        <label for="model">模型:</label>
        <input id="model" type="text" bind:value={newEndpoint.model} />
      </div>
      <div class="form-group">
        <label for="apiKey">API密钥:</label>
        <input id="apiKey" type="password" bind:value={newEndpoint.apiKey} />
      </div>
      <button on:click={addEndpoint} disabled={isLoading}>保存</button>
    </div>
  {/if}

  <button on:click={testAllEndpoints} disabled={isLoading}>
    {isLoading ? '测试中...' : '测试所有端点'}
  </button>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if testResults.length > 0}
    <div class="test-results">
      <h2>测试结果</h2>
      {#each testResults as result}
        <div class="result-item">
          <h3>{result.name}</h3>
          <p>延迟: {result.latency >= 0 ? result.latency.toFixed(2) + 's' : '测试失败'}</p>
          <p>结果: {result.result}</p>
        </div>
      {/each}
    </div>
  {/if}
</main>
