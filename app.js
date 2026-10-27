(() => {
  'use strict';

  /* ============================================================
     Utilities
     ============================================================ */

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const round = (value, digits = 0) => Number(Number(value).toFixed(digits));
  const rand = (min, max) => min + Math.random() * (max - min);
  const pad2 = (value) => String(value).padStart(2, '0');
  const fmt = (value, digits = 0) => Number(value).toFixed(digits);
  const fmtInt = (value) => Math.round(value).toLocaleString('zh-CN');

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[character]));
  }

  function icon(name, extraClass = '') {
    return `<svg class="icon ${extraClass}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
  }

  function formatDate(date = new Date()) {
    return `${date.getFullYear()}.${pad2(date.getMonth() + 1)}.${pad2(date.getDate())}`;
  }

  function formatTime(date = new Date()) {
    return `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
  }

  function formatDateTime(date = new Date()) {
    return `${formatDate(date)} ${formatTime(date)}`;
  }

  function hexToRgba(hex, alpha) {
    const clean = String(hex).replace('#', '');
    const full = clean.length === 3 ? clean.split('').map((character) => character + character).join('') : clean;
    const parsed = parseInt(full, 16);
    return `rgba(${(parsed >> 16) & 255}, ${(parsed >> 8) & 255}, ${parsed & 255}, ${alpha})`;
  }

  function getPath(object, path) {
    return String(path).split('.').reduce((value, key) => (value == null ? undefined : value[key]), object);
  }

  function setText(target, value) {
    const element = typeof target === 'string' ? $(target) : target;
    if (element) element.textContent = String(value);
  }

  function getStoredTheme() {
    try {
      return localStorage.getItem('nexus-cockpit-theme');
    } catch (error) {
      return null;
    }
  }

  function storeTheme(theme) {
    try {
      localStorage.setItem('nexus-cockpit-theme', theme);
    } catch (error) {
      /* optional persistence */
    }
  }

  /* ============================================================
     Module definitions
     ============================================================ */

  const CDC_MODULES = [
    {
      id: 'soc',
      index: '01',
      name: 'SOC 核心监控',
      en: 'SOC CORE',
      icon: 'cpu',
      color: '#4C8DFF',
      rgb: '76,141,255',
      subtitle: '12 核 CPU · GPU · NPU · MPU · 欠压 / ECC / 频率跳变',
      cardMetrics: [
        { live: 'soc.cpuAvg', label: 'CPU 平均负载', unit: '%', digits: 1 },
        { live: 'soc.gpu', label: 'GPU 占用', unit: '%', digits: 0 },
        { live: 'soc.temp', label: '封装温度', unit: '°C', digits: 1 }
      ],
      chartCaption: 'CPU / GPU / NPU 实时负载'
    },
    {
      id: 'ddr',
      index: '02',
      name: 'DDR 运行内存',
      en: 'DDR MEMORY',
      icon: 'memory',
      color: '#A855F7',
      rgb: '168,85,247',
      subtitle: '4 CH Logic · 8 / 16 BANK · 容量型号匹配 · 日志解析器',
      cardMetrics: [
        { live: 'ddr.usage', label: '内存占用', unit: '%', digits: 1 },
        { live: 'ddr.jump', label: '跳变幅度', unit: '%', digits: 1 },
        { live: 'ddr.bandwidth', label: '总带宽', unit: 'GB/s', digits: 1 }
      ],
      chartCaption: '4 通道占用率'
    },
    {
      id: 'storage',
      index: '03',
      name: '存储健康检测',
      en: 'UFS STORAGE',
      icon: 'storage',
      color: '#22D3EE',
      rgb: '34,211,238',
      subtitle: 'UFS 40 物理块图谱 · 坏块区域 · 读写延迟 · 寿命',
      cardMetrics: [
        { live: 'storage.usage', label: '存储占用', unit: '%', digits: 1 },
        { live: 'storage.bad', label: '坏块数量', unit: '块', digits: 0 },
        { live: 'storage.latency', label: '读延迟', unit: 'ms', digits: 1 }
      ],
      chartCaption: 'UFS 读写吞吐'
    },
    {
      id: 'rf',
      index: '04',
      name: '射频短距离',
      en: 'RF & CONNECTIVITY',
      icon: 'radio',
      color: '#F59E0B',
      rgb: '245,158,11',
      subtitle: '2G / 3G / 4G / 5G / WiFi / 蓝牙 / NFC · 天线自检',
      cardMetrics: [
        { live: 'rf.rsrp5g', label: '5G RSRP', unit: 'dBm', digits: 0 },
        { live: 'rf.wifiRssi', label: 'WiFi RSSI', unit: 'dBm', digits: 0 },
        { live: 'rf.btRssi', label: 'BT RSSI', unit: 'dBm', digits: 0 }
      ],
      chartCaption: '多制式信号强度'
    },
    {
      id: 'display',
      index: '05',
      name: '显示监控区',
      en: 'DISPLAY MONITOR',
      icon: 'monitor',
      color: '#38BDF8',
      rgb: '56,189,248',
      subtitle: '仪表屏 · 中控屏 · 副驾屏 · 后排屏 · HUG · SerDes 链路 / 刷新率',
      cardMetrics: [
        { value: '5 / 5', label: '屏幕在线', unit: '' },
        { value: '60', label: '平均刷新', unit: 'Hz' },
        { value: '5 / 5', label: 'SerDes 锁定', unit: '' }
      ],
      chartCaption: '五屏刷新率与链路状态'
    },
    {
      id: 'audio',
      index: '06',
      name: '音频显示区',
      en: 'AUDIO & A2B',
      icon: 'audio',
      color: '#EC4899',
      rgb: '236,72,153',
      subtitle: 'A2B 节点寄存器 · FM / AM · MIC 阵列检测',
      cardMetrics: [
        { live: 'audio.jitter', label: 'A2B Jitter', unit: 'ms', digits: 1 },
        { live: 'audio.micLevels.2', label: 'MIC3 电平', unit: 'dB', digits: 0 },
        { live: 'audio.fmSignal', label: 'FM 信号', unit: 'dBμV', digits: 0 }
      ],
      chartCaption: 'MIC 阵列实时电平'
    },
    {
      id: 'peripherals',
      index: '07',
      name: '外设区',
      en: 'PERIPHERALS',
      icon: 'monitor',
      color: '#34D399',
      rgb: '52,211,153',
      subtitle: 'Camera · TI 981 / 983 · 摄像头链路',
      cardMetrics: [
        { live: 'peripherals.camFps', label: '前视 FPS', unit: '/30', digits: 0 },
        { live: 'peripherals.drop', label: '丢帧计数', unit: '帧', digits: 0 },
        { live: 'peripherals.camCount', label: '在线摄像头', unit: '路', digits: 0 }
      ],
      chartCaption: '摄像头实时帧率'
    },
    {
      id: 'mcu',
      index: '08',
      name: 'MCU 监控区',
      en: 'MCU MONITOR',
      icon: 'chip',
      color: '#FB923C',
      rgb: '251,146,60',
      subtitle: 'ADC · 风扇 · CAN · PCIe · 安全岛 / RDA / NRDA',
      cardMetrics: [
        { live: 'mcu.adc4', label: 'ADC CH4', unit: 'V', digits: 2 },
        { live: 'mcu.canLoad', label: 'CAN 负载', unit: '%', digits: 0 },
        { live: 'mcu.hbRda', label: 'RDA 心跳', unit: 'Hz', digits: 0 }
      ],
      chartCaption: 'ADC 电压与三核心跳'
    },
    {
      id: 'stability',
      index: '09',
      name: '稳定性监控',
      en: 'STABILITY',
      icon: 'activity',
      color: '#FB7185',
      rgb: '251,113,133',
      subtitle: 'panic · 异常重启 · ANR · crash · 动态事件绘图',
      cardMetrics: [
        { live: 'stability.panic', label: 'Panic', unit: '次', digits: 0 },
        { live: 'stability.reboot', label: '异常重启', unit: '次', digits: 0 },
        { live: 'stability.anr', label: 'ANR', unit: '次', digits: 0 }
      ],
      chartCaption: '24h 稳定性事件'
    },
    {
      id: 'power',
      index: '10',
      name: '功耗监控区',
      en: 'POWER & THERMAL',
      icon: 'zap',
      color: '#A3E635',
      rgb: '163,230,53',
      subtitle: '整机功率 · 温度伴随跳变 · 电源轨拆解',
      cardMetrics: [
        { live: 'power.total', label: '整机功耗', unit: 'W', digits: 1 },
        { live: 'power.temp', label: 'SoC 温度', unit: '°C', digits: 1 },
        { live: 'power.peak', label: '峰值功率', unit: 'W', digits: 1 }
      ],
      chartCaption: '功率与温度伴随曲线'
    },
    {
      id: 'ota',
      index: '11',
      name: '诊断与 OTA',
      en: 'DIAGNOSTICS & OTA',
      icon: 'refresh',
      color: '#60A5FA',
      rgb: '96,165,250',
      subtitle: 'UDS · DoIP · 版本一致性 · 升级成功率 · 分区校验',
      cardMetrics: [
        { value: 'OK', label: 'UDS 会话', unit: '', source: 'CAN/DoIP 3E 00', threshold: '超时即告警' },
        { value: '一致', label: '版本一致性', unit: '', source: 'getprop 分区版本', threshold: '不一致即告警' },
        { value: '100', label: 'OTA 成功率', unit: '%', source: '升级记录', threshold: '< 95% 告警' }
      ],
      chartCaption: '诊断会话与升级趋势'
    },
    {
      id: 'timesync',
      index: '12',
      name: '时间同步与网络',
      en: 'TIMESYNC & NETWORK',
      icon: 'wifi',
      color: '#F472B6',
      rgb: '244,114,182',
      subtitle: 'PTP / gPTP · 时间跳变 · 以太网链路 · 丢包 · TSN 队列',
      cardMetrics: [
        { value: '0.6', label: 'PTP 偏移', unit: 'µs', source: 'pmc / gPTP', threshold: '> 100µs 告警' },
        { value: '0', label: '时间跳变', unit: '次', source: '系统时钟差分', threshold: '单次 > 1s 告警' },
        { value: '0.2', label: '丢包率', unit: '%', source: '网关 ping 统计', threshold: '> 5% 告警' }
      ],
      chartCaption: '时间偏移与链路质量'
    }
  ];

  const MDC_MODULES = [
    {
      id: 'mdc-compute', index: 'M01', domain: 'mdc', name: 'MDC SoC 计算核心', en: 'MDC COMPUTE', icon: 'cpu',
      color: '#22D3EE', rgb: '34,211,238', subtitle: '8 核 CPU · 双 NPU · GPU · 锁步安全岛',
      cardMetrics: [
        { live: 'mdc.cpuAvg', label: 'CPU 平均负载', unit: '%', digits: 0 },
        { live: 'mdc.npu0', label: 'NPU0 占用', unit: '%', digits: 0 },
        { live: 'mdc.temp', label: '封装温度', unit: '°C', digits: 1 }
      ],
      chartCaption: 'CPU / NPU / GPU 实时负载',
      detail: {
        chart: 'mdcCompute',
        stats: [
          { label: 'CPU 平均负载', live: 'mdc.cpuAvg', unit: '%', digits: 0 },
          { label: 'NPU0 占用', live: 'mdc.npu0', unit: '%', digits: 0 },
          { label: 'NPU1 占用', live: 'mdc.npu1', unit: '%', digits: 0 },
          { label: 'GPU 占用', live: 'mdc.gpu', unit: '%', digits: 0 },
          { label: '封装温度', live: 'mdc.temp', unit: '°C', digits: 1 },
          { label: '域控功耗', live: 'mdc.power', unit: 'W', digits: 1 }
        ],
        tableTitle: 'AI 加速与安全资源', tableHeaders: ['单元', '占用', '温度', '状态'],
        rows: [
          ['CPU Cluster', '<span data-live="mdc.cpuAvg" data-digits="0">--</span>%', '<span data-live="mdc.temp" data-digits="1">--</span>°C', '<span class="status-pill healthy">正常</span>'],
          ['NPU 0 · BEV', '<span data-live="mdc.npu0" data-digits="0">--</span>%', '78°C', '<span class="status-pill warning">热降频</span>'],
          ['NPU 1 · Planning', '<span data-live="mdc.npu1" data-digits="0">--</span>%', '73°C', '<span class="status-pill healthy">正常</span>'],
          ['GPU · ISP', '<span data-live="mdc.gpu" data-digits="0">--</span>%', '69°C', '<span class="status-pill healthy">正常</span>'],
          ['锁步安全岛', '<span data-live="mdc.lockstep" data-digits="0">--</span> mismatch', '—', '<span class="status-pill warning">关注</span>']
        ],
        notes: ['NPU0 已触发热降频，BEV 推理队列迁移至 NPU1。', '锁步核出现 2 次 mismatch，安全岛接管降级链路。']
      }
    },
    {
      id: 'mdc-ddr', index: 'M02', domain: 'mdc', name: 'MDC DDR / LPDDR5X', en: 'MDC MEMORY', icon: 'memory',
      color: '#38BDF8', rgb: '56,189,248', subtitle: '4 CH LPDDR5X · BEV 帧缓冲 · ECC 监控',
      cardMetrics: [
        { live: 'mdc.ddrUsage', label: '内存占用', unit: '%', digits: 1 },
        { live: 'mdc.ddrBandwidth', label: '总带宽', unit: 'GB/s', digits: 1 },
        { live: 'mdc.ddrEcc', label: 'ECC CE', unit: '次', digits: 0 }
      ],
      chartCaption: '4 通道带宽与 ECC',
      detail: {
        chart: 'mdcDdr',
        stats: [
          { label: 'DDR 占用', live: 'mdc.ddrUsage', unit: '%', digits: 1 },
          { label: '总带宽', live: 'mdc.ddrBandwidth', unit: 'GB/s', digits: 1 },
          { label: 'ECC CE', live: 'mdc.ddrEcc', unit: '次', digits: 0 },
          { label: 'DDR 温度', live: 'mdc.ddrTemp', unit: '°C', digits: 1 }
        ],
        tableTitle: '4 通道带宽分配', tableHeaders: ['通道', '占用', '带宽', 'ECC'],
        rows: [
          ['CH0 · BEV', '<span data-live="mdc.ddrCh0" data-digits="1">--</span>%', '<span data-live="mdc.ddrBw0" data-digits="1">--</span> GB/s', '0'],
          ['CH1 · Planning', '<span data-live="mdc.ddrCh1" data-digits="1">--</span>%', '<span data-live="mdc.ddrBw1" data-digits="1">--</span> GB/s', '1'],
          ['CH2 · Map', '<span data-live="mdc.ddrCh2" data-digits="1">--</span>%', '<span data-live="mdc.ddrBw2" data-digits="1">--</span> GB/s', '4'],
          ['CH3 · Log', '<span data-live="mdc.ddrCh3" data-digits="1">--</span>%', '<span data-live="mdc.ddrBw3" data-digits="1">--</span> GB/s', '0']
        ],
        notes: ['CH2 地图缓存带宽跳变 18%，与 BEV 帧缓冲同窗口。', 'ECC CE 集中在 CH2，建议锁定地址区间。']
      }
    },
    {
      id: 'mdc-storage', index: 'M03', domain: 'mdc', name: 'MDC 模型存储', en: 'MDC STORAGE', icon: 'storage',
      color: '#818CF8', rgb: '129,140,248', subtitle: 'NVMe / 模型分区 · 加载时延 · 坏块',
      cardMetrics: [
        { live: 'mdc.storageUsage', label: '模型占用', unit: '%', digits: 1 },
        { live: 'mdc.modelLatency', label: '模型加载', unit: 'ms', digits: 0 },
        { live: 'mdc.storageRead', label: '读带宽', unit: 'MB/s', digits: 0 }
      ],
      chartCaption: '模型读取与加载时延',
      detail: {
        chart: 'mdcStorage',
        stats: [
          { label: '存储占用', live: 'mdc.storageUsage', unit: '%', digits: 1 },
          { label: '模型加载', live: 'mdc.modelLatency', unit: 'ms', digits: 0 },
          { label: '读带宽', live: 'mdc.storageRead', unit: 'MB/s', digits: 0 },
          { label: '坏块', live: 'mdc.storageBad', unit: '块', digits: 0 }
        ],
        tableTitle: '模型分区健康', tableHeaders: ['分区', '大小', '读延迟', '状态'],
        rows: [
          ['BEV Perception', '18.4 GB', '<span data-live="mdc.modelLatency" data-digits="0">--</span> ms', '<span class="status-pill warning">关注</span>'],
          ['Planning / Control', '6.2 GB', '42 ms', '<span class="status-pill healthy">正常</span>'],
          ['HD Map Tile', '12.8 GB', '38 ms', '<span class="status-pill healthy">正常</span>'],
          ['Diagnostic Log', '4.0 GB', '22 ms', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['BEV 模型加载 128ms，超过 100ms 冷启动门限。', 'NVMe 健康余量 91%，无新增不可纠正坏块。']
      }
    },
    {
      id: 'mdc-perception', index: 'M04', domain: 'mdc', name: 'MDC 感知链路', en: 'PERCEPTION CHAIN', icon: 'radar',
      color: '#2DD4BF', rgb: '45,212,191', subtitle: 'Camera · LiDAR · Radar · USS · 时间同步',
      cardMetrics: [
        { value: '8 / 8', label: 'Camera 在线', unit: '' },
        { live: 'mdc.sensorLatency', label: '感知时延', unit: 'ms', digits: 0 },
        { live: 'mdc.lidarDrop', label: 'LiDAR 丢点', unit: '%', digits: 1 }
      ],
      chartCaption: '感知帧率与点云丢点',
      detail: {
        chart: 'mdcPerception',
        stats: [
          { value: '8 / 8', label: 'Camera 在线', unit: '' },
          { value: '2 / 2', label: 'LiDAR 在线', unit: '' },
          { label: '感知时延', live: 'mdc.sensorLatency', unit: 'ms', digits: 0 },
          { label: 'LiDAR 丢点', live: 'mdc.lidarDrop', unit: '%', digits: 1 }
        ],
        tableTitle: '传感器链路', tableHeaders: ['传感器', '链路', '时延', '状态'],
        rows: [
          ['Front Camera 8MP', 'MIPI CSI-2 ×4', '48 ms', '<span class="status-pill warning">延迟</span>'],
          ['Side Cameras ×4', 'GMSL2', '21 ms', '<span class="status-pill healthy">正常</span>'],
          ['LiDAR ×2', '1000BASE-T1', '<span data-live="mdc.lidarDrop" data-digits="1">--</span>% drop', '<span class="status-pill warning">丢点</span>'],
          ['Radar ×5', 'CAN FD', '12 ms', '<span class="status-pill healthy">正常</span>'],
          ['USS ×12', 'LIN', '18 ms', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['前视 Camera 端到端 48ms，超过 35ms 融合门限。', '左侧 LiDAR 点云丢点 4.2%，需清洁窗口/检查线束。']
      }
    },
    {
      id: 'mdc-network', index: 'M05', domain: 'mdc', name: 'MDC 以太网 / TSN', en: 'ETH / TSN / PCIe', icon: 'activity',
      color: '#60A5FA', rgb: '96,165,250', subtitle: '车载以太网 · TSN · PTP · PCIe 带宽',
      cardMetrics: [
        { live: 'mdc.ethLatency', label: 'TSN 时延', unit: 'μs', digits: 0 },
        { live: 'mdc.packetLoss', label: '丢包率', unit: '%', digits: 2 },
        { live: 'mdc.ptpOffset', label: 'PTP 偏差', unit: 'μs', digits: 1 }
      ],
      chartCaption: 'TSN 时延与丢包',
      detail: {
        chart: 'mdcNetwork',
        stats: [
          { label: 'TSN 时延', live: 'mdc.ethLatency', unit: 'μs', digits: 0 },
          { label: '丢包率', live: 'mdc.packetLoss', unit: '%', digits: 2 },
          { label: 'PTP 偏差', live: 'mdc.ptpOffset', unit: 'μs', digits: 1 },
          { label: 'PCIe 代宽', value: 'Gen4 ×8', unit: '' }
        ],
        tableTitle: '以太网 / TSN 端口', tableHeaders: ['端口', '速率', '丢包', '状态'],
        rows: [
          ['ETH0 · Camera', '10 Gbps', '0.08%', '<span class="status-pill healthy">LOCK</span>'],
          ['ETH1 · LiDAR', '10 Gbps', '0.02%', '<span class="status-pill healthy">LOCK</span>'],
          ['ETH2 · CDC', '1 Gbps', '0.80%', '<span class="status-pill warning">关注</span>'],
          ['PCIe · SoC↔Switch', 'Gen4 ×8', 'CRC 0', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['ETH2 与 CDC 的跨域链路出现 0.8% 丢包。', 'PTP 偏差 1.8μs，超过 1.0μs 门限，可能影响融合时间戳。']
      }
    },
    {
      id: 'mdc-safety', index: 'M06', domain: 'mdc', name: 'MDC 功能安全', en: 'FUNCTIONAL SAFETY', icon: 'shield',
      color: '#F472B6', rgb: '244,114,182', subtitle: '锁步核 · 安全岛 · watchdog · E2E · ASIL-D',
      cardMetrics: [
        { live: 'mdc.lockstep', label: '锁步 mismatch', unit: '次', digits: 0 },
        { live: 'mdc.watchdog', label: 'Watchdog', unit: '次', digits: 0 },
        { value: 'ASIL-D', label: '安全等级', unit: '' }
      ],
      chartCaption: '安全心跳与锁步状态',
      detail: {
        chart: 'mdcSafety',
        stats: [
          { label: '锁步 mismatch', live: 'mdc.lockstep', unit: '次', digits: 0 },
          { label: 'Watchdog', live: 'mdc.watchdog', unit: '次', digits: 0 },
          { label: '安全心跳', live: 'mdc.heartbeat', unit: 'Hz', digits: 0 },
          { label: 'E2E CRC 错误', value: '2', unit: '次' }
        ],
        tableTitle: '安全机制自检', tableHeaders: ['检查项', '观测值', '门限', '结果'],
        rows: [
          ['锁步核对比', '<span data-live="mdc.lockstep" data-digits="0">--</span> mismatch', '0', '<span class="status-pill warning">关注</span>'],
          ['安全岛心跳', '<span data-live="mdc.heartbeat" data-digits="0">--</span> Hz', '60 ± 2Hz', '<span class="status-pill healthy">正常</span>'],
          ['E2E CRC', '2 errors', '0', '<span class="status-pill warning">关注</span>'],
          ['Watchdog', '<span data-live="mdc.watchdog" data-digits="0">--</span> resets', '0', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['锁步核 1 出现 2 次 mismatch，已触发安全岛降级。', '建议复现并抓取锁步比较器原始日志。']
      }
    },
    {
      id: 'mdc-power', index: 'M07', domain: 'mdc', name: 'MDC 功耗与散热', en: 'POWER & THERMAL', icon: 'zap',
      color: '#FBBF24', rgb: '251,191,36', subtitle: 'SoC 功耗 · 结温 · 风扇 · 电源轨',
      cardMetrics: [
        { live: 'mdc.power', label: '域控功耗', unit: 'W', digits: 1 },
        { live: 'mdc.temp', label: 'SoC 温度', unit: '°C', digits: 1 },
        { live: 'mdc.fan', label: '风扇转速', unit: 'RPM', digits: 0 }
      ],
      chartCaption: '功耗与温度伴随曲线',
      detail: {
        chart: 'mdcPower',
        stats: [
          { label: '域控功耗', live: 'mdc.power', unit: 'W', digits: 1 },
          { label: 'SoC 温度', live: 'mdc.temp', unit: '°C', digits: 1 },
          { label: '风扇转速', live: 'mdc.fan', unit: 'RPM', digits: 0 },
          { label: '峰值功耗', value: '86.2', unit: 'W' }
        ],
        tableTitle: '电源轨拆解', tableHeaders: ['电源轨', '电压', '电流', '状态'],
        rows: [
          ['VCORE', '0.82 V', '26.4 A', '<span class="status-pill warning">瞬态尖峰</span>'],
          ['LPDDR5X', '1.05 V', '9.2 A', '<span class="status-pill healthy">正常</span>'],
          ['NPU 0/1', '0.78 V', '18.6 A', '<span class="status-pill warning">高负载</span>'],
          ['Peripheral', '3.3 V', '4.2 A', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['VCORE 瞬态功率 86.2W，与 NPU 热降频同窗口。', '风扇已提升至 5200 RPM，温度仍高于 78°C。']
      }
    }
  ];

  const VDC_MODULES = [
    {
      id: 'vdc-soc', index: 'V01', domain: 'vdc', name: 'VDC SoC / MCU 核心', en: 'VDC CONTROL CORE', icon: 'chip',
      color: '#A3E635', rgb: '163,230,53', subtitle: '车控 SoC · 安全岛 · 双核锁步 · ECC',
      cardMetrics: [
        { live: 'vdc.cpuLoad', label: 'CPU 负载', unit: '%', digits: 0 },
        { live: 'vdc.safetyIsland', label: '安全岛心跳', unit: 'Hz', digits: 0 },
        { live: 'vdc.temp', label: 'SoC 温度', unit: '°C', digits: 1 }
      ],
      chartCaption: '车控 CPU 与安全岛心跳',
      detail: {
        chart: 'vdcSoc',
        stats: [
          { label: 'CPU 负载', live: 'vdc.cpuLoad', unit: '%', digits: 0 },
          { label: '安全岛心跳', live: 'vdc.safetyIsland', unit: 'Hz', digits: 0 },
          { label: 'ECC CE', live: 'vdc.ecc', unit: '次', digits: 0 },
          { label: 'SoC 温度', live: 'vdc.temp', unit: '°C', digits: 1 },
          { label: '域控功耗', live: 'vdc.power', unit: 'W', digits: 1 },
          { label: '三核心跳', live: 'vdc.heartbeat', unit: 'Hz', digits: 0 }
        ],
        tableTitle: '车控核心与安全岛', tableHeaders: ['核心', '负载/心跳', '温度', '状态'],
        rows: [
          ['Cortex-A 核', '<span data-live="vdc.cpuLoad" data-digits="0">--</span>%', '<span data-live="vdc.temp" data-digits="1">--</span>°C', '<span class="status-pill healthy">正常</span>'],
          ['Cortex-R 安全核', '<span data-live="vdc.safetyIsland" data-digits="0">--</span> Hz', '61°C', '<span class="status-pill healthy">LOCKSTEP</span>'],
          ['CAN 控制器', '<span data-live="vdc.canLoad" data-digits="0">--</span>%', '—', '<span class="status-pill warning">负载偏高</span>'],
          ['IO 协处理器', '<span data-live="vdc.ioLatency" data-digits="1">--</span> ms', '—', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['VDC 主核 ECC 计数为 0，安全岛心跳稳定。', 'CAN 控制器负载 78%，建议限流非关键周期报文。']
      }
    },
    {
      id: 'vdc-io', index: 'V02', domain: 'vdc', name: 'VDC 车身 IO', en: 'BODY IO / ACTUATOR', icon: 'layers',
      color: '#34D399', rgb: '52,211,153', subtitle: '门 / 窗 / 灯 / 座椅 / 后视镜 · 执行器',
      cardMetrics: [
        { live: 'vdc.doorFaults', label: '门控故障', unit: '项', digits: 0 },
        { live: 'vdc.lightFaults', label: '灯光故障', unit: '项', digits: 0 },
        { live: 'vdc.ioLatency', label: 'IO 响应', unit: 'ms', digits: 1 }
      ],
      chartCaption: '车身 IO 响应时延',
      detail: {
        chart: 'vdcIo',
        stats: [
          { label: '门控故障', live: 'vdc.doorFaults', unit: '项', digits: 0 },
          { label: '灯光故障', live: 'vdc.lightFaults', unit: '项', digits: 0 },
          { label: 'IO 响应', live: 'vdc.ioLatency', unit: 'ms', digits: 1 },
          { label: '执行器故障', live: 'vdc.actuatorFaults', unit: '项', digits: 0 }
        ],
        tableTitle: '车身 IO 通道', tableHeaders: ['通道', '状态', '响应', '结果'],
        rows: [
          ['左前门 / 车窗', 'LOCK', '8 ms', '<span class="status-pill healthy">正常</span>'],
          ['右后门 / LIN', '3 次超时', '22 ms', '<span class="status-pill warning">观察</span>'],
          ['外部灯光', '全部在线', '6 ms', '<span class="status-pill healthy">正常</span>'],
          ['座椅 / 后视镜', '位置反馈正常', '12 ms', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['右后门 LIN 节点 24h 内 3 次超时，未导致功能丢失。', '车身 IO 响应均值 8ms，处于 20ms 门限内。']
      }
    },
    {
      id: 'vdc-chassis', index: 'V03', domain: 'vdc', name: 'VDC 底盘接口', en: 'CHASSIS INTERFACE', icon: 'gauge',
      color: '#FBBF24', rgb: '251,191,36', subtitle: '制动 · 转向 · 扭矩 · 悬架 · EPB',
      cardMetrics: [
        { live: 'vdc.brakePressure', label: '制动压力', unit: 'bar', digits: 0 },
        { live: 'vdc.steeringAngle', label: '转向角', unit: '°', digits: 1 },
        { live: 'vdc.torque', label: '扭矩请求', unit: 'N·m', digits: 0 }
      ],
      chartCaption: '底盘信号实时曲线',
      detail: {
        chart: 'vdcChassis',
        stats: [
          { label: '制动压力', live: 'vdc.brakePressure', unit: 'bar', digits: 0 },
          { label: '转向角', live: 'vdc.steeringAngle', unit: '°', digits: 1 },
          { label: '扭矩请求', live: 'vdc.torque', unit: 'N·m', digits: 0 },
          { label: '悬架高度', live: 'vdc.suspension', unit: 'mm', digits: 0 }
        ],
        tableTitle: '底盘执行器状态', tableHeaders: ['系统', '观测值', '响应', '状态'],
        rows: [
          ['ESP / ABS', '压力建立正常', '12 ms', '<span class="status-pill healthy">正常</span>'],
          ['EPS 转向', '角度跟踪误差 0.3°', '8 ms', '<span class="status-pill healthy">正常</span>'],
          ['电驱扭矩', '<span data-live="vdc.torque" data-digits="0">--</span> N·m', '16 ms', '<span class="status-pill healthy">正常</span>'],
          ['空气悬架', '高度偏差 2 mm', '35 ms', '<span class="status-pill warning">观察</span>']
        ],
        notes: ['制动与转向链路响应正常，无 ASIL 相关故障。', '空气悬架高度偏差 2mm，建议下次保养检查气泵。']
      }
    },
    {
      id: 'vdc-network', index: 'V04', domain: 'vdc', name: 'VDC CAN / LIN / ETH', en: 'VEHICLE NETWORK', icon: 'activity',
      color: '#22D3EE', rgb: '34,211,238', subtitle: 'CAN FD · LIN · 车载以太网 · 网关',
      cardMetrics: [
        { live: 'vdc.canLoad', label: 'CAN 负载', unit: '%', digits: 0 },
        { live: 'vdc.linTimeouts', label: 'LIN 超时', unit: '次', digits: 0 },
        { value: '1 / 1', label: '以太网链路', unit: '' }
      ],
      chartCaption: 'CAN 负载与 LIN 错误',
      detail: {
        chart: 'vdcNetwork',
        stats: [
          { label: 'CAN 负载', live: 'vdc.canLoad', unit: '%', digits: 0 },
          { label: 'LIN 超时', live: 'vdc.linTimeouts', unit: '次', digits: 0 },
          { label: '以太网链路', value: '1 / 1', unit: '' },
          { label: '网关时延', live: 'vdc.ioLatency', unit: 'ms', digits: 1 }
        ],
        tableTitle: '总线与网关', tableHeaders: ['总线', '负载/速率', '错误', '状态'],
        rows: [
          ['CAN FD 0', '<span data-live="vdc.canLoad" data-digits="0">--</span>%', '14 错误帧', '<span class="status-pill warning">关注</span>'],
          ['CAN FD 1', '46%', '2 错误帧', '<span class="status-pill healthy">正常</span>'],
          ['LIN 0/1', '<span data-live="vdc.linTimeouts" data-digits="0">--</span> 超时', 'CRC 1', '<span class="status-pill warning">观察</span>'],
          ['网关 ETH', '1 Gbps', '0 丢包', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['CAN FD 0 负载 78%，网关已开始限制非关键报文。', 'LIN 右后门节点 24h 超时 3 次，建议检查接插件。']
      }
    },
    {
      id: 'vdc-power', index: 'V05', domain: 'vdc', name: 'VDC 电源管理', en: 'POWER MANAGEMENT', icon: 'zap',
      color: '#FB923C', rgb: '251,146,60', subtitle: '12V / 48V · DC-DC · 静态电流 · 继电器',
      cardMetrics: [
        { live: 'vdc.voltage12', label: '12V 电压', unit: 'V', digits: 2 },
        { live: 'vdc.quiescent', label: '静态电流', unit: 'mA', digits: 0 },
        { live: 'vdc.dcDc', label: 'DC-DC 输出', unit: 'V', digits: 2 }
      ],
      chartCaption: '12V 电压与静态电流',
      detail: {
        chart: 'vdcPower',
        stats: [
          { label: '12V 电压', live: 'vdc.voltage12', unit: 'V', digits: 2 },
          { label: '静态电流', live: 'vdc.quiescent', unit: 'mA', digits: 0 },
          { label: 'DC-DC 输出', live: 'vdc.dcDc', unit: 'V', digits: 2 },
          { label: '域控功耗', live: 'vdc.power', unit: 'W', digits: 1 }
        ],
        tableTitle: '电源轨与继电器', tableHeaders: ['电源轨', '观测值', '门限', '状态'],
        rows: [
          ['12V 常电', '<span data-live="vdc.voltage12" data-digits="2">--</span> V', '11.5 - 13.0V', '<span class="status-pill warning">瞬态跌落</span>'],
          ['48V 轻混', '47.8 V', '42 - 54V', '<span class="status-pill healthy">正常</span>'],
          ['DC-DC', '<span data-live="vdc.dcDc" data-digits="2">--</span> V', '13.5 ± 0.3V', '<span class="status-pill healthy">正常</span>'],
          ['主继电器', '闭合', 'CLOSED', '<span class="status-pill healthy">正常</span>']
        ],
        notes: ['12V 在冷启动瞬间跌至 11.72V，未触发欠压复位。', '静态电流 18mA，低于 30mA 目标。']
      }
    },
    {
      id: 'vdc-diagnostics', index: 'V06', domain: 'vdc', name: 'VDC 诊断 / OTA', en: 'UDS / OTA', icon: 'file',
      color: '#C084FC', rgb: '192,132,252', subtitle: 'DTC · UDS 会话 · OTA 进度 · 诊断记录',
      cardMetrics: [
        { live: 'vdc.dtc', label: '活动 DTC', unit: '条', digits: 0 },
        { value: 'Extended', label: 'UDS 会话', unit: '' },
        { live: 'vdc.ota', label: 'OTA 进度', unit: '%', digits: 0 }
      ],
      chartCaption: 'DTC 与 OTA 状态',
      detail: {
        chart: 'vdcDiag',
        stats: [
          { label: '活动 DTC', live: 'vdc.dtc', unit: '条', digits: 0 },
          { label: 'UDS 会话', value: 'Extended', unit: '' },
          { label: 'OTA 进度', live: 'vdc.ota', unit: '%', digits: 0 },
          { label: '诊断请求', live: 'vdc.diagReq', unit: '/min', digits: 0 }
        ],
        tableTitle: '活动诊断故障码', tableHeaders: ['DTC', '模块', '状态', '建议'],
        rows: [
          ['U0100', 'ECM / VCU 通信', '<span class="status-pill critical">当前</span>', '检查 CAN 终端电阻'],
          ['B1325', '车身电源', '<span class="status-pill warning">历史</span>', '复核 12V 瞬态'],
          ['U3000', '控制模块', '<span class="status-pill warning">待确认</span>', '执行 UDS 自检'],
          ['P0AFA', 'BMS 绝缘', '<span class="status-pill healthy">已恢复</span>', '持续观察']
        ],
        notes: ['U0100 与 CAN FD 0 高负载同时出现。', 'OTA 包已下载 72%，建议在 12V 稳定后继续。']
      }
    },
    {
      id: 'vdc-stability', index: 'V07', domain: 'vdc', name: 'VDC 稳定性', en: 'STABILITY', icon: 'shield',
      color: '#FB7185', rgb: '251,113,133', subtitle: 'Watchdog · 复位 · 故障 · 启动自检',
      cardMetrics: [
        { live: 'vdc.resets', label: '异常复位', unit: '次', digits: 0 },
        { live: 'vdc.faults', label: '当前故障', unit: '项', digits: 0 },
        { live: 'vdc.heartbeat', label: '主心跳', unit: 'Hz', digits: 0 }
      ],
      chartCaption: '复位与故障事件',
      detail: {
        chart: 'vdcStability',
        stats: [
          { label: '异常复位', live: 'vdc.resets', unit: '次', digits: 0 },
          { label: '当前故障', live: 'vdc.faults', unit: '项', digits: 0 },
          { label: '主心跳', live: 'vdc.heartbeat', unit: 'Hz', digits: 0 },
          { label: '启动自检', value: 'PASS', unit: '' }
        ],
        tableTitle: '稳定性自检', tableHeaders: ['检查项', '观测值', '门限', '结果'],
        rows: [
          ['Watchdog', '0 次喂狗失败', '0', '<span class="status-pill healthy">正常</span>'],
          ['MPU / 栈保护', '0 次越界', '0', '<span class="status-pill healthy">正常</span>'],
          ['启动自检', 'PASS', 'PASS', '<span class="status-pill healthy">通过</span>'],
          ['异常复位', '<span data-live="vdc.resets" data-digits="0">--</span> 次', '0', '<span class="status-pill warning">观察</span>']
        ],
        notes: ['VDC 启动自检通过，无栈越界或 MPU 异常。', '异常复位 1 次，需结合 12V 瞬态与 U0100 联合分析。']
      }
    }
  ];

  const DOMAINS = {
    cdc: { id: 'cdc', code: 'CDC', name: '智能座舱域', en: 'COCKPIT DOMAIN', icon: 'monitor', color: '#4C8DFF', rgb: '76,141,255' },
    mdc: { id: 'mdc', code: 'MDC', name: '智能驾驶域', en: 'DRIVING DOMAIN', icon: 'chip', color: '#22D3EE', rgb: '34,211,238' },
    vdc: { id: 'vdc', code: 'VDC', name: '智能车控域', en: 'VEHICLE CONTROL', icon: 'layers', color: '#A3E635', rgb: '163,230,53' }
  };
  const DOMAIN_ORDER = ['cdc', 'mdc', 'vdc'];
  const MODULE_DEFS = [
    ...CDC_MODULES.map((module) => ({ ...module, domain: 'cdc' })),
    ...MDC_MODULES,
    ...VDC_MODULES
  ];

  /* ============================================================
     Sample diagnostic log
     The parser is intentionally independent from the renderer:
     raw text -> regex -> fields -> module events.
     ============================================================ */

  // 指标采集源与告警阈值（对应 docs/MONITORING-SPEC.md 第三节）
  const METRIC_SPEC = {
    soc: [['/proc/stat', '> 85% 持续 60s', '5s', 10], ['scaling_cur_freq', '< 50% 标称且非温控', '5s', 10], ['thermal_zone', '≥ 95°C', '5s', 20]],
    ddr: [['/proc/meminfo', '> 90% 持续 5min', '10s', 10], ['ECC 计数', 'CE > 10/24h', '60s', 25], ['PMU 带宽', '> 90% 峰值', '5s', 10]],
    storage: [['statvfs /data', '< 5%', '60s', 10], ['UFS health', '新增 ≥ 1', '30min', 20], ['/proc/diskstats', 'P99 > 200ms', '5min', 15]],
    rf: [['cmd wifi', '< -80dBm 持续 1min', '10s', 10], ['dumpsys telephony', '< -115dBm', '10s', 15], ['系统重连统计', '> 3 次/5min', '5min', 10]],
    display: [['dumpsys display / DRM', '任一屏离线 > 5s', '10s', 25], ['SerDes 寄存器', '失锁或重训 > 2 次/min', '5s', 20], ['解串器温度', '> 85°C', '30s', 10]],
    audio: [['dumpsys audio', '服务异常/重启', '30s', 20], ['A2B 节点寄存器', '任一节点掉线', '10s', 25], ['功放 I2C 诊断', '过温 / 过流', '30s', 20]],
    peripherals: [['video 节点 + HAL', '任一路掉线', '10s', 20], ['HAL 帧统计', '< 20fps 持续 10s', '5s', 15], ['SerDes 误码', '持续增长', '5s', 20]],
    mcu: [['串口 / SPI 心跳', '丢 ≥ 2 拍', '1s', 25], ['CAN 驱动统计', '> 85% 或错误帧', '5s', 15], ['UDS 19 02', '新增 DTC', '5min', 15]],
    stability: [['boot reason', '非计划重启', '每次启动', 30], ['logcat -b crash', '新增即记', '60s', 20], ['lowmemorykiller', '杀进程事件', '5min', 10]],
    power: [['PMIC ADC', '< 9V 或 > 16V', '1s', 25], ['thermal_zone', '≥ 95°C', '5s', 20], ['cpufreq 事件', '非预期降频', '5s', 10]],
    ota: [['CAN/DoIP 3E 00', '超时即告警', '30s', 20], ['getprop 分区版本', '不一致即告警', '每次启动', 15], ['升级记录', '< 95% 告警', '每次 OTA', 25]],
    timesync: [['pmc / gPTP', '> 100µs 告警', '10s', 20], ['系统时钟差分', '单次 > 1s 告警', '10s', 25], ['网关 ping 统计', '> 5% 告警', '60s', 10]]
  };
  CDC_MODULES.forEach((module) => {
    const spec = METRIC_SPEC[module.id];
    if (!spec) return;
    module.cardMetrics = module.cardMetrics.map((metric, index) =>
      spec[index]
        ? { ...metric, source: spec[index][0], threshold: spec[index][1], period: spec[index][2], weight: spec[index][3] }
        : metric
    );
  });

  function monitorSpecPanel(target) {
    const def = MODULE_DEFS.find((item) => item.id === (target && target.id)) || {};
    const rows = (def.cardMetrics || []).filter((metric) => metric.source);
    if (!rows.length) return '';
    const body = rows.map((metric) =>
      '<tr><td class="strong">' + escapeHtml(metric.label) + '</td>'
      + '<td class="mono">' + escapeHtml(metric.source) + '</td>'
      + '<td class="mono">' + escapeHtml(metric.period || '—') + '</td>'
      + '<td>' + escapeHtml(metric.threshold || '—') + '</td>'
      + '<td class="mono">' + (metric.weight == null ? '—' : metric.weight) + '</td></tr>'
    ).join('');
    return panelHTML('监控与诊断方案', 'scan',
      '<div class="table-scroll"><table class="data-table" style="min-width:640px">'
      + '<thead><tr><th>指标</th><th>采集源</th><th>周期</th><th>告警阈值</th><th>权重</th></tr></thead>'
      + '<tbody>' + body + '</tbody></table></div>',
      { span2: true, sub: 'SOURCE / PERIOD / THRESHOLD / WEIGHT' });
  }

  const SAMPLE_LOG = `2026-10-24 10:29:58.104 [SOC] [INFO] code=SOC_BOOT cpu=12 gpu=1 npu=1 mpu=2
2026-10-24 10:30:12.220 [STABILITY] [INFO] code=STB_BOOT uptime=842s boot=normal
2026-10-24 10:30:20.018 [RF] [INFO] code=RF_BAND band=n78,b41,wifi6e state=on
2026-10-24 10:30:30.410 [POWER] [INFO] code=PWR_TOTAL total=42.4W temp=58C
2026-10-24 10:30:45.882 [PERIPH] [INFO] code=CAM_FPS cam=front fps=30 drop=0
2026-10-24 10:30:55.120 [DDR] [INFO] code=DDR_MODEL model=LPDDR5-6400 cap=8G chl=4 bank=16
2026-10-24 10:31:02.040 [MCU] [WARN] code=MCU_ADC channel=4 voltage=4.62V threshold=4.5V
2026-10-24 10:31:03.118 [MCU] [ERROR] code=MCU_HEARTBEAT core=RDA missed=2
2026-10-24 10:31:08.662 [SOC] [WARN] code=SOC_CPU_JUMP core=7 freq=2.4GHz prev=1.8GHz jump=33%
2026-10-24 10:31:11.208 [AUDIO] [WARN] code=A2B_REG node=3 reg=0x2C val=0x1A expected=0x1E
2026-10-24 10:31:12.090 [AUDIO] [ERROR] code=A2B_LINK node=3 crc=7 latency=2.4ms
2026-10-24 10:31:40.510 [UFS] [INFO] code=UFS_HEALTH life=91% bad=3
2026-10-24 10:31:55.222 [STABILITY] [ERROR] code=STB_ANR app=com.nexus.ivi timeout=5s
2026-10-24 10:32:01.044 [STABILITY] [FATAL] code=STB_CRASH signal=SIGSEGV proc=ivi
2026-10-24 10:32:10.886 [MCU] [WARN] code=MCU_CAN load=78% errors=14
2026-10-24 10:32:14.326 [SOC] [ERROR] code=SOC_CPU_UV core=3 vdd=0.71V threshold=0.75V duration=12ms
2026-10-24 10:32:17.770 [POWER] [WARN] code=PWR_SPIKE rail=VCORE power=68.1W delta=+25.7W
2026-10-24 10:32:18.902 [POWER] [WARN] code=PWR_TEMP temp=84C threshold=80C
2026-10-24 10:32:19.010 [SOC] [ERROR] code=SOC_ECC_CE unit=l2slice2 count=12 corrected=1
2026-10-24 10:32:21.440 [DDR] [WARN] code=DDR_JUMP ch=2 bank=7 usage=91.2% jump=18.4%
2026-10-24 10:32:22.012 [DDR] [ERROR] code=DDR_ECC ch=2 bank=7 ce=4 ue=0
2026-10-24 10:32:33.908 [RF] [WARN] code=RF_RSRP band=n78 rsrp=-112dBm threshold=-105dBm
2026-10-24 10:32:34.120 [RF] [ERROR] code=RF_ANT antenna=main resistance=8.4ohm threshold=5ohm
2026-10-24 10:32:48.560 [PERIPH] [ERROR] code=CAM_DROP cam=front fps=24 drop=18
2026-10-24 10:32:49.008 [PERIPH] [WARN] code=SERDES_LOCK display=center chip=983 link=unstable
2026-10-24 10:33:02.402 [SOC] [INFO] code=SOC_GPU_TEMP gpu=67C limit=85C
2026-10-24 10:33:05.190 [POWER] [INFO] code=PWR_RAIL rail=DDR power=9.2W
2026-10-24 10:33:15.650 [UFS] [WARN] code=UFS_BAD_BLOCK lun=0 pba=0x0000A3 count=3
2026-10-24 10:33:16.040 [UFS] [ERROR] code=UFS_LATENCY read=48ms p99=112ms
2026-10-24 10:33:30.110 [PERIPH] [WARN] code=HUD_REFRESH hud=1 fps=48
2026-10-24 10:33:42.990 [AUDIO] [WARN] code=AUDIO_MIC mic=3 level=-58dB threshold=-45dB
2026-10-24 10:34:01.080 [AUDIO] [INFO] code=AUDIO_FM freq=98.7MHz rds=1
2026-10-24 10:34:02.720 [AUDIO] [WARN] code=AUDIO_AM freq=990kHz snr=12dB
2026-10-24 10:34:10.330 [DDR] [WARN] code=DDR_JUMP ch=0 bank=3 usage=88.7% jump=9.2%
2026-10-24 10:34:22.008 [MCU] [INFO] code=MCU_FAN rpm=3200 pwm=62%
2026-10-24 10:34:44.200 [STABILITY] [ERROR] code=STB_REBOOT reason=watchdog count=2
2026-10-24 10:34:55.520 [RF] [INFO] code=RF_BT rssi=-71dBm profile=a2dp
2026-10-24 10:35:02.470 [UFS] [WARN] code=UFS_WEAR block=0x0000A3 wear=87%
2026-10-24 10:35:20.330 [PERIPH] [INFO] code=USB_PORT port=2 speed=5Gbps
2026-10-24 10:35:44.660 [POWER] [WARN] code=PWR_FAN fan=4100 state=high
2026-10-24 10:35:55.780 [MCU] [WARN] code=MCU_PCIE lane=4 speed=Gen3 retrain=2
2026-10-24 10:36:01.260 [RF] [WARN] code=RF_NFC nfc=disabled antenna=shared
2026-10-24 10:36:10.888 [STABILITY] [FATAL] code=STB_PANIC kernel=watchdog_hardlockup
2026-10-24 10:36:44.080 [SOC] [WARN] code=SOC_NPU_THROTTLE npu=81C freq=1.0GHz
2026-10-24 10:37:05.440 [POWER] [INFO] code=PWR_TOTAL total=48.2W temp=76C
2026-10-24 10:38:01.120 [MDC] [WARN] code=MDC_SOC_ECC core=5 ce=8
2026-10-24 10:38:05.240 [MDC] [ERROR] code=MDC_NPU_THROTTLE npu=86C freq=1.2GHz
2026-10-24 10:38:09.360 [MDC] [WARN] code=MDC_DDR_BW ch=2 bandwidth=42.8GB/s drop=6%
2026-10-24 10:38:12.480 [MDC] [WARN] code=MDC_MODEL_LOAD model=bev_v4 latency=128ms
2026-10-24 10:38:15.600 [MDC] [ERROR] code=MDC_CAM_LATENCY cam=front latency=48ms
2026-10-24 10:38:18.720 [MDC] [WARN] code=MDC_LIDAR_DROP lidar=left drop=4.2%
2026-10-24 10:38:21.840 [MDC] [ERROR] code=MDC_ETH_LOSS port=2 loss=0.80%
2026-10-24 10:38:24.960 [MDC] [WARN] code=MDC_PTP_OFFSET offset=1.8us threshold=1.0us
2026-10-24 10:38:28.080 [MDC] [ERROR] code=MDC_SAFETY_LOCKSTEP core=1 mismatch=2
2026-10-24 10:38:31.200 [MDC] [WARN] code=MDC_POWER_SPIKE power=86.2W delta=+18.4W
2026-10-24 10:38:34.320 [MDC] [WARN] code=MDC_FAN rpm=5200 temp=79C
2026-10-24 10:39:01.100 [VDC] [ERROR] code=VDC_HEARTBEAT core=RDA missed=2
2026-10-24 10:39:04.200 [VDC] [WARN] code=VDC_CAN_LOAD bus=CAN0 load=78% errors=14
2026-10-24 10:39:07.300 [VDC] [WARN] code=VDC_LIN_TIMEOUT node=RL-door count=3
2026-10-24 10:39:10.400 [VDC] [WARN] code=VDC_12V_DIP voltage=11.72V threshold=11.8V
2026-10-24 10:39:13.500 [VDC] [ERROR] code=VDC_IO_FAULT channel=RL-window response=42ms
2026-10-24 10:39:16.600 [VDC] [WARN] code=VDC_DTC dtc=U0100 count=4
2026-10-24 10:39:19.700 [VDC] [INFO] code=VDC_OTA progress=72% target=vdc-2.4.1
2026-10-24 10:39:22.800 [VDC] [WARN] code=VDC_SUSPENSION height=2mm threshold=1mm
2026-10-24 10:39:25.900 [VDC] [ERROR] code=VDC_WATCHDOG reset=1 reason=12V-dip
2026-10-24 10:39:29.000 [VDC] [WARN] code=VDC_CHASSIS torque=210N.m response=18ms`;

  const TAG_TO_MODULE = {
    SOC: 'soc',
    DDR: 'ddr',
    UFS: 'storage',
    STORAGE: 'storage',
    RF: 'rf',
    AUDIO: 'audio',
    PERIPH: 'peripherals',
    PERIPHERALS: 'peripherals',
    MCU: 'mcu',
    STABILITY: 'stability',
    POWER: 'power',
    MDC: 'mdc-compute',
    VDC: 'vdc-soc'
  };

  const CODE_TO_MODULE = {
    MDC_SOC_ECC: 'mdc-compute',
    MDC_NPU_THROTTLE: 'mdc-compute',
    MDC_DDR_BW: 'mdc-ddr',
    MDC_MODEL_LOAD: 'mdc-storage',
    MDC_CAM_LATENCY: 'mdc-perception',
    MDC_LIDAR_DROP: 'mdc-perception',
    MDC_ETH_LOSS: 'mdc-network',
    MDC_PTP_OFFSET: 'mdc-network',
    MDC_SAFETY_LOCKSTEP: 'mdc-safety',
    MDC_POWER_SPIKE: 'mdc-power',
    MDC_FAN: 'mdc-power',
    VDC_HEARTBEAT: 'vdc-soc',
    VDC_CAN_LOAD: 'vdc-network',
    VDC_LIN_TIMEOUT: 'vdc-network',
    VDC_12V_DIP: 'vdc-power',
    VDC_IO_FAULT: 'vdc-io',
    VDC_DTC: 'vdc-diagnostics',
    VDC_OTA: 'vdc-diagnostics',
    VDC_SUSPENSION: 'vdc-chassis',
    VDC_WATCHDOG: 'vdc-stability',
    VDC_CHASSIS: 'vdc-chassis'
  };

  const EVENT_META = {
    SOC_BOOT: { title: 'SOC 上电初始化完成', detail: '12 核 CPU、GPU、NPU 与 MPU 已全部上线。' },
    SOC_CPU_JUMP: { title: 'CPU 频率阶跃跳变', detail: 'Core {core} 频率由 {prev} 跳变至 {freq}，偏差 {jump}，触发频率稳定度采样。', severity: 'warning' },
    SOC_CPU_UV: { title: 'CPU3 欠压跳变', detail: 'VDD_CPU 瞬态跌落至 {vdd}，低于 {threshold} 门限，持续 {duration}，触发 PMIC 保护计数。', severity: 'critical' },
    SOC_ECC_CE: { title: 'L2 ECC 可纠正错误', detail: '{unit} 可纠正 ECC 计数升至 {count}，当前均已被硬件纠正。', severity: 'critical' },
    SOC_GPU_TEMP: { title: 'GPU 温度采样', detail: 'GPU 当前 {gpu}，距离 {limit} 温度墙仍有裕量。' },
    SOC_NPU_THROTTLE: { title: 'NPU 热降频', detail: 'NPU 温度达到 {npu}，频率已降至 {freq}，推理队列自动迁移至 MPU。', severity: 'warning' },
    DDR_MODEL: { title: 'DDR 型号与容量匹配', detail: '内存型号匹配为 {model}，容量 {cap}，拓扑 {chl} 通道 × {bank} BANK。' },
    DDR_JUMP: { title: 'DDR 通道占用跳变', detail: 'CH{ch} BANK{bank} 占用率 {usage}，瞬时跳变 {jump}，已触发带宽仲裁采样。', severity: 'warning' },
    DDR_ECC: { title: 'DDR 通道 ECC 异常', detail: 'CH{ch} BANK{bank} 可纠正错误 {ce} 次，不可纠正错误 {ue} 次。', severity: 'critical' },
    UFS_HEALTH: { title: 'UFS 健康度采样', detail: 'UFS 寿命余量 {life}，累计坏块 {bad} 块。' },
    UFS_BAD_BLOCK: { title: 'UFS 新增坏块', detail: 'LUN{lun} PBA {pba} 检测到 {count} 个坏块，已进入重映射队列。', severity: 'warning' },
    UFS_LATENCY: { title: 'UFS 读延迟超门限', detail: '顺序读 {read}，P99 延迟 {p99}，超过座舱启动门限。', severity: 'critical' },
    UFS_WEAR: { title: 'UFS 物理块磨损', detail: '物理块 {block} 擦写寿命已使用 {wear}，建议提前迁移冷数据。', severity: 'warning' },
    RF_BAND: { title: '射频频段注册', detail: '{band} 频段与 WiFi 6E 状态 {state}，天线驻波自检已排队。' },
    RF_RSRP: { title: '5G RSRP 低于门限', detail: 'Band {band} RSRP {rsrp}，低于 {threshold}，触发分集天线切换。', severity: 'warning' },
    RF_ANT: { title: '主天线连通性异常', detail: '{antenna} 天线阻抗 {resistance}，超过 {threshold} 门限，疑似线束或接插件异常。', severity: 'critical' },
    RF_BT: { title: '蓝牙链路状态', detail: 'BT RSSI {rssi}，Profile {profile} 保持连接。' },
    RF_NFC: { title: 'NFC 天线共享冲突', detail: 'NFC 当前 {nfc}，与 {antenna} 天线共享导致读卡距离下降。', severity: 'warning' },
    A2B_REG: { title: 'A2B 节点寄存器异常', detail: 'Node {node} REG {reg} 当前值 {val}，期望 {expected}，链路 CRC 进入观察。', severity: 'warning' },
    A2B_LINK: { title: 'A2B 总线误码', detail: 'Node {node} CRC 错误 {crc} 次，传输时延 {latency}。', severity: 'critical' },
    AUDIO_MIC: { title: 'MIC3 电平偏低', detail: 'MIC {mic} 当前 {level}，低于 {threshold}，疑似麦克风孔堵塞或偏置异常。', severity: 'warning' },
    AUDIO_FM: { title: 'FM 接收正常', detail: 'FM {freq} 锁定成功，RDS {rds}。' },
    AUDIO_AM: { title: 'AM 信噪比偏低', detail: 'AM {freq} 信噪比 {snr}，低于舒适接收门限。', severity: 'warning' },
    CAM_FPS: { title: 'Camera 帧率正常', detail: '{cam} 摄像头 {fps} FPS，丢帧 {drop}。' },
    CAM_DROP: { title: '前视摄像头掉帧', detail: '{cam} 摄像头帧率降至 {fps}，累计丢帧 {drop}，SerDes 链路进入观察。', severity: 'critical' },
    SERDES_LOCK: { title: 'SerDes 链路锁定不稳', detail: '{display} 显示屏 {chip} 解串链路 {link}，FPD-Link IV 重训练计数上升。', severity: 'warning' },
    HUD_REFRESH: { title: 'HUD 刷新率异常', detail: 'HUD{hud} 当前刷新率 {fps}，低于 60Hz 标称值。', severity: 'warning' },
    USB_PORT: { title: 'USB 端口识别', detail: 'USB Port {port} 以 {speed} 枚举成功。' },
    MCU_ADC: { title: 'MCU ADC 采样越限', detail: 'ADC 通道 {channel} 电压 {voltage}，超过 {threshold} 门限。', severity: 'warning' },
    MCU_HEARTBEAT: { title: 'RDA 核心心跳丢失', detail: '{core} 核心心跳丢失 {missed} 拍，安全岛已接管降级策略。', severity: 'critical' },
    MCU_CAN: { title: 'CAN 总线负载偏高', detail: 'CAN 负载 {load}，错误帧 {errors}，网关开始限流。', severity: 'warning' },
    MCU_FAN: { title: '风扇调速采样', detail: '风扇 {rpm} RPM，PWM {pwm}。' },
    MCU_PCIE: { title: 'PCIe 链路重训练', detail: 'PCIe Gen3 ×{lane} 发生 {retrain} 次重训练，需检查信号完整性。', severity: 'warning' },
    STB_BOOT: { title: '系统启动完成', detail: '当前 uptime {uptime}，启动模式 {boot}。' },
    STB_ANR: { title: 'IVI 应用 ANR', detail: '{app} 主线程超时 {timeout}，系统已生成 traces。', severity: 'critical' },
    STB_CRASH: { title: 'IVI 进程崩溃', detail: '{proc} 收到 {signal}，崩溃栈已归档。', severity: 'critical' },
    STB_REBOOT: { title: '异常重启', detail: '重启原因 {reason}，当日累计 {count} 次。', severity: 'critical' },
    STB_PANIC: { title: 'Kernel Panic', detail: '内核触发 {kernel}，已进入 dump 采集流程。', severity: 'critical' },
    PWR_TOTAL: { title: '整机功耗采样', detail: '整机功耗 {total}，SoC 温度 {temp}。' },
    PWR_SPIKE: { title: 'VCORE 功耗瞬态尖峰', detail: '{rail} 轨功耗 {power}，瞬态增量 {delta}，与 CPU3 欠压时间窗重合。', severity: 'warning' },
    PWR_TEMP: { title: 'SoC 温度越限', detail: '封装温度 {temp}，超过 {threshold} 温度墙，触发调频。', severity: 'warning' },
    PWR_RAIL: { title: '电源轨功耗', detail: '{rail} 轨功耗 {power}。' },
    PWR_FAN: { title: '风扇高速运行', detail: '风扇 {fan} RPM，散热状态 {state}。', severity: 'warning' },
    MDC_SOC_ECC: { title: 'MDC SoC ECC 可纠正错误', detail: 'Core {core} 检测到 {ce} 次 ECC CE，安全岛已记录地址。', severity: 'warning' },
    MDC_NPU_THROTTLE: { title: 'MDC NPU 热降频', detail: 'NPU 温度达到 {npu}，频率降至 {freq}，BEV 队列迁移。', severity: 'critical' },
    MDC_DDR_BW: { title: 'MDC DDR 带宽跳变', detail: 'CH{ch} 带宽 {bandwidth}，瞬时下降 {drop}，帧缓冲进入观察。', severity: 'warning' },
    MDC_MODEL_LOAD: { title: 'BEV 模型加载超时', detail: '模型 {model} 加载耗时 {latency}，超过 100ms 冷启动门限。', severity: 'warning' },
    MDC_CAM_LATENCY: { title: '前视 Camera 感知时延', detail: '{cam} Camera 端到端时延 {latency}，超过融合门限。', severity: 'critical' },
    MDC_LIDAR_DROP: { title: 'LiDAR 点云丢点', detail: '{lidar} LiDAR 点云丢点 {drop}，链路与窗口需检查。', severity: 'warning' },
    MDC_ETH_LOSS: { title: 'MDC 以太网丢包', detail: 'Port {port} 丢包率 {loss}，跨域链路进入降级。', severity: 'critical' },
    MDC_PTP_OFFSET: { title: 'PTP 时间同步偏差', detail: 'PTP 偏差 {offset}，超过 {threshold} 门限，影响融合时间戳。', severity: 'warning' },
    MDC_SAFETY_LOCKSTEP: { title: '锁步核 mismatch', detail: 'Core {core} 锁步比较 mismatch {mismatch} 次，安全岛接管。', severity: 'critical' },
    MDC_POWER_SPIKE: { title: 'MDC 功耗瞬态尖峰', detail: '域控功耗 {power}，瞬态增量 {delta}，与 NPU 降频同窗口。', severity: 'warning' },
    MDC_FAN: { title: 'MDC 风扇高速运行', detail: '风扇 {rpm} RPM，SoC 温度 {temp}。', severity: 'warning' },
    VDC_HEARTBEAT: { title: 'VDC 三核心跳丢失', detail: '{core} 核心心跳丢失 {missed} 拍，安全岛降级。', severity: 'critical' },
    VDC_CAN_LOAD: { title: 'VDC CAN 负载偏高', detail: '{bus} 负载 {load}，错误帧 {errors}，网关限流。', severity: 'warning' },
    VDC_LIN_TIMEOUT: { title: 'VDC LIN 节点超时', detail: '{node} 节点 24h 超时 {count} 次，功能未丢失。', severity: 'warning' },
    VDC_12V_DIP: { title: '12V 电源瞬态跌落', detail: '12V 电压 {voltage}，低于 {threshold}，未触发复位。', severity: 'warning' },
    VDC_IO_FAULT: { title: '车身 IO 响应超时', detail: '{channel} 响应 {response}，超过 20ms 门限。', severity: 'critical' },
    VDC_DTC: { title: 'VDC 活动故障码', detail: 'DTC {dtc}，当前活动故障 {count} 条，需执行 UDS 自检。', severity: 'warning' },
    VDC_OTA: { title: 'VDC OTA 下载进度', detail: 'OTA 目标 {target}，当前进度 {progress}，等待 12V 稳定。' },
    VDC_SUSPENSION: { title: '空气悬架高度偏差', detail: '悬架高度偏差 {height}，超过 {threshold}，建议检查气泵。', severity: 'warning' },
    VDC_WATCHDOG: { title: 'VDC 异常复位', detail: '复位原因 {reason}，累计 {reset} 次，需联合电源分析。', severity: 'critical' },
    VDC_CHASSIS: { title: '底盘扭矩接口采样', detail: '扭矩请求 {torque}，响应 {response}，链路正常。' }
  };

  /* ============================================================
     State
     ============================================================ */

  const CAPACITY_PROFILES = {
    '4': { label: '4 GB', model: 'LPDDR4X-4266', channels: 4, banks: 8, width: '16-bit', rank: '2 Rank', speed: '4266 MT/s' },
    '6': { label: '6 GB', model: 'LPDDR4X-4266', channels: 4, banks: 8, width: '16-bit', rank: '2 Rank', speed: '4266 MT/s' },
    '8': { label: '8 GB', model: 'LPDDR5-6400', channels: 4, banks: 16, width: '16-bit', rank: '2 Rank', speed: '6400 MT/s' },
    '16': { label: '16 GB', model: 'LPDDR5-6400', channels: 4, banks: 16, width: '16-bit', rank: '4 Rank', speed: '6400 MT/s' },
    '32': { label: '32 GB', model: 'LPDDR5X-8533', channels: 4, banks: 16, width: '16-bit', rank: '4 Rank', speed: '8533 MT/s' }
  };

  const RF_RADIOS = [    { id: '2g', name: '2G GSM', band: 'B3 / B8', live: 'rf.rsrp2g', quality: 34, state: '待机', enabled: false },
    { id: '3g', name: '3G WCDMA', band: 'B1 / B8', live: 'rf.rsrp3g', quality: 42, state: '待机', enabled: false },
    { id: '4g', name: '4G LTE', band: 'B1 / B3 / B41', live: 'rf.rsrp4g', quality: 72, state: '已注册', enabled: true },
    { id: '5g', name: '5G NR', band: 'n78 / n41', live: 'rf.rsrp5g', quality: 64, state: '已注册', enabled: true },
    { id: 'wifi', name: 'WiFi 6E', band: '2.4 / 5 / 6 GHz', live: 'rf.wifiRssi', quality: 83, state: '已连接', enabled: true },
    { id: 'bt', name: '蓝牙 5.3', band: '2.4 GHz', live: 'rf.btRssi', quality: 68, state: 'A2DP', enabled: true },
    { id: 'nearlink', name: '星闪 / 绿牙', band: '2.4 / 5.8 GHz', live: 'rf.nearlinkRssi', quality: 74, state: '已连接', enabled: true },
    { id: 'nfc', name: 'NFC', band: '13.56 MHz', live: 'rf.nfcRssi', quality: 46, state: '共享天线', enabled: true }
  ];

  const RF_BANDS = [
    { label: '5G n1', on: true }, { label: '5G n3', on: true }, { label: '5G n28', on: true }, { label: '5G n41', on: true },
    { label: '5G n77', on: false }, { label: '5G n78', on: true }, { label: '5G n79', on: false }, { label: 'LTE B1', on: true },
    { label: 'LTE B3', on: true }, { label: 'LTE B8', on: false }, { label: 'WiFi 2.4G', on: true }, { label: 'WiFi 5G', on: true },
    { label: 'WiFi 6E', on: true }, { label: 'BT 2.4G', on: true }, { label: '星闪 5.8G', on: true }, { label: 'NFC 13.56M', on: true },
    { label: 'GNSS L1/L5', on: true }
  ];

  const ANTENNAS = [
    { name: '主天线 MAIN', resistance: '8.4 Ω', status: '阻抗超差', warn: true },
    { name: '分集天线 DIV', resistance: '1.2 Ω', status: '通过', warn: false },
    { name: 'GNSS L1/L5', resistance: '1.5 Ω', status: '通过', warn: false },
    { name: 'WiFi / BT', resistance: '0.8 Ω', status: '通过', warn: false },
    { name: 'NFC 共享', resistance: '1.1 Ω', status: '通过', warn: false }
  ];

  const A2B_NODES = [
    { name: 'Head Unit', addr: '0x68', role: 'Master', latency: '1.2 ms', status: 'ok' },
    { name: 'Amplifier', addr: '0x69', role: 'Slave', latency: '1.6 ms', status: 'ok' },
    { name: 'MIC Array', addr: '0x6A', role: 'Slave', latency: '2.4 ms', status: 'warn' },
    { name: 'ANC Module', addr: '0x6B', role: 'Slave', latency: '1.8 ms', status: 'ok' }
  ];

  const A2B_REGISTERS = [
    { node: 'Node 3', reg: '0x2C', value: '0x1A', expected: '0x1E', status: 'warn' },
    { node: 'Node 3', reg: '0x30', value: '0x0F', expected: '0x0F', status: 'ok' },
    { node: 'Node 3', reg: '0x34', value: '0x07', expected: '0x07', status: 'ok' },
    { node: 'Node 2', reg: '0x14', value: '0x22', expected: '0x22', status: 'ok' },
    { node: 'Node 2', reg: '0x18', value: '0x3A', expected: '0x3A', status: 'ok' },
    { node: 'Node 1', reg: '0x08', value: '0x01', expected: '0x01', status: 'ok' },
    { node: 'Node 0', reg: '0x00', value: '0x68', expected: '0x68', status: 'ok' },
    { node: 'Node 0', reg: '0x04', value: '0x1F', expected: '0x1F', status: 'ok' }
  ];

  const CAMERAS = [
    { name: '前视摄像头', resolution: '8 MP · 4K', fps: 24, target: 30, drop: 18, link: 'MIPI CSI-2', status: 'warn' },
    { name: '后视摄像头', resolution: '2 MP · 1080P', fps: 30, target: 30, drop: 0, link: 'MIPI CSI-2', status: 'ok' },
    { name: 'DMS 摄像头', resolution: '2 MP · 940nm', fps: 30, target: 30, drop: 0, link: 'MIPI CSI-2', status: 'ok' },
    { name: 'OMS 摄像头', resolution: '2 MP · 广角', fps: 30, target: 30, drop: 1, link: 'MIPI CSI-2', status: 'ok' }
  ];

  const DISPLAYS = [
    { name: '仪表屏', size: '12.3"', resolution: '1920 × 720', serdes: 'TI 981 / 983', iface: 'MIPI DSI', link: 'LOCK', temperature: 52, status: 'ok' },
    { name: '中控屏', size: '15.6"', resolution: '2560 × 1440', serdes: 'TI 981 / 983', iface: 'MIPI DSI', link: '不稳定', temperature: 61, status: 'warn' },
    { name: '副驾屏', size: '12.3"', resolution: '1920 × 720', serdes: 'TI 981 / 983', iface: 'MIPI DSI', link: 'LOCK', temperature: 49, status: 'ok' },
    { name: '后排屏', size: '15.6"', resolution: '1920 × 1080', serdes: 'TI 981 / 983', iface: 'MIPI DSI', link: 'LOCK', temperature: 47, status: 'ok' },
    { name: 'HUD（HUG）', size: '抬头显', resolution: '1280 × 480', serdes: 'TI 981 / 983', iface: 'FPD-Link IV', link: '48Hz', temperature: 45, status: 'warn' }
  ];

  const USB_PORTS = [
    { name: 'USB-C 前排', speed: 'USB 3.2 Gen2 · 10Gbps', power: 'PD 65W', device: 'U 盘 / 手机', status: 'ok' },
    { name: 'USB-A 后排', speed: 'USB 3.2 Gen1 · 5Gbps', power: 'BC 1.2 · 7.5W', device: '充电中', status: 'ok' }
  ];

  const MCU_ADC_CHANNELS = [
    { name: 'CH0 · VBAT', value: 12.04, unit: 'V', threshold: 13.0, warn: false },
    { name: 'CH1 · 5V', value: 5.02, unit: 'V', threshold: 5.5, warn: false },
    { name: 'CH2 · 3.3V', value: 3.31, unit: 'V', threshold: 3.6, warn: false },
    { name: 'CH3 · 1.8V', value: 1.79, unit: 'V', threshold: 2.0, warn: false },
    { name: 'CH4 · 12V AUX', value: 4.62, unit: 'V', threshold: 4.5, warn: true },
    { name: 'CH5 · 5V USB', value: 5.08, unit: 'V', threshold: 5.5, warn: false },
    { name: 'CH6 · 3.3V IO', value: 3.28, unit: 'V', threshold: 3.6, warn: false },
    { name: 'CH7 · 1.2V DDR', value: 1.21, unit: 'V', threshold: 1.4, warn: false }
  ];

  const ADC_LIVE_KEYS = [null, null, null, null, 'mcu.adc4', null, null, null];

  const MODULE_ACTIONS = {
    soc: [
      { title: '检查 PMIC 瞬态补偿', detail: '将 VCORE 下限补偿提高 20mV，复测 CPU3 欠压窗口。' },
      { title: '收敛 Core7 频点跳变', detail: '限制 1.8↔2.4GHz 阶跃斜率，观察 ECC 计数是否回落。' },
      { title: '执行 L2 ECC 地址追踪', detail: '对 l2slice2 错误地址做 30 分钟定向压力测试。' }
    ],
    ddr: [
      { title: '迁移高带宽帧缓冲', detail: '将 Camera 帧缓冲从 CH2 迁移至 CH0/CH1，降低仲裁冲突。' },
      { title: '限制 CH2 峰值带宽', detail: '设置 8GB 型号下 CH2 带宽上限，观察跳变幅度。' },
      { title: '复核容量 / BANK 映射', detail: '确认 LPDDR5-6400 4CH × 16BANK 与日志解析结果一致。' }
    ],
    storage: [
      { title: '执行坏块重映射', detail: '将 PBA 0x0000A3 重映射至预留块，并保留 4 个备用块。' },
      { title: '迁移高风险冷数据', detail: '优先迁移磨损率高于 80% 的物理块数据。' },
      { title: '复测 P99 读延迟', detail: '全盘扫描 2 轮，目标 P99 < 40ms。' }
    ],
    rf: [
      { title: '更换主天线线束', detail: '重点检查接插件与走线弯折，目标阻抗 < 5Ω。' },
      { title: '切换分集天线', detail: '在 n78 频段临时使用 DIV 天线，恢复 5G 链路预算。' },
      { title: '执行全频段 VSWR 自检', detail: '覆盖 5G / LTE / WiFi / BT / NFC 共享天线。' }
    ],
    audio: [
      { title: '复核 A2B Node3 寄存器', detail: '将 0x2C 从 0x1A 恢复至 0x1E，观察 CRC 是否清零。' },
      { title: '检查 MIC3 声学通道', detail: '清理麦克风孔并复测偏置电压与 -58dB 电平。' },
      { title: '验证 FM / AM 天线', detail: '检查调谐器接地与 AM 信噪比，目标 SNR > 20dB。' }
    ],
    peripherals: [
      { title: '重插中控 SerDes 线束', detail: '检查 TI 981 / 983 链路接插件与屏蔽层接地。' },
      { title: '执行链路重训练', detail: '对中控屏 FPD-Link IV 进行眼图与重训练计数复测。' },
      { title: '清洁前视摄像头', detail: '清洁镜头后执行静态校准，目标 FPS 恢复 30。' }
    ],
    mcu: [
      { title: '检查 RDA 心跳链路', detail: '复测 RDA 供电与 SPI 心跳，定位 2 拍丢失原因。' },
      { title: '核验 ADC CH4 分压', detail: '检查 12V AUX 分压电阻，确认 4.62V 是否真实越限。' },
      { title: '限制 CAN 峰值负载', detail: '关闭非关键周期报文，目标负载 < 65%。' }
    ],
    stability: [
      { title: '抓取 tombstone / dmesg', detail: '固化 IVI SIGSEGV 与 watchdog hardlockup 现场。' },
      { title: '关闭非关键后台服务', detail: '降低启动阶段内存与 IO 竞争，观察 ANR 是否复现。' },
      { title: '执行 12h Monkey 回归', detail: '注入异常重启与低内存场景，目标 0 panic。' }
    ],
    power: [
      { title: '提前风扇介入点', detail: '将 80°C 温度墙前移至 76°C，提升高负载散热余量。' },
      { title: '限制 GPU 峰值功耗', detail: '将 GPU 峰值限制在 70%，避免 VCORE 瞬态尖峰。' },
      { title: '复核电源轨纹波', detail: '测量 VCORE / DDR 轨纹波，确认与 CPU 欠压的相关性。' }
    ],
    'mdc-compute': [
      { title: '迁移 BEV 推理队列', detail: '将 NPU0 热区模型迁移至 NPU1，降低 81°C 热点负载。' },
      { title: '复核锁步 mismatch', detail: '抓取安全岛比较器日志，定位 Core1 mismatch 根因。' },
      { title: '执行 30 分钟算力压测', detail: '同时加载 BEV + Planning，观察温度与 ECC 趋势。' }
    ],
    'mdc-perception': [
      { title: '检查前视 Camera 链路', detail: '复测 MIPI CSI-2 与 GMSL2 链路，目标时延 < 35ms。' },
      { title: '清洁 LiDAR 窗口', detail: '清除左侧 LiDAR 窗口污染并复测点云完整率。' },
      { title: '复核 PTP 时间戳', detail: '将 PTP 偏差收敛至 1.0μs 以内，避免融合错帧。' }
    ],
    'mdc-network': [
      { title: '隔离 ETH2 跨域流量', detail: '限制 CDC 到 MDC 的非关键流量，降低 0.8% 丢包。' },
      { title: '重配 TSN 调度', detail: '为 Camera/LiDAR 流量预留时间片，降低抖动。' },
      { title: '检查 PTP 主时钟', detail: '复核 Grandmaster 与 PHC 补偿，目标偏差 < 1μs。' }
    ],
    'mdc-safety': [
      { title: '冻结安全岛现场', detail: '保存锁步 mismatch 与 E2E CRC 错误快照。' },
      { title: '执行安全机制自检', detail: '覆盖 lockstep / watchdog / E2E / 电压监控。' },
      { title: '评估 ASIL 降级策略', detail: '确认 MDC 降级后仍满足 L2+ 最小风险策略。' }
    ],
    'vdc-soc': [
      { title: '复核 RDA 心跳', detail: '检查 Cortex-R 心跳与安全岛 SPI 链路。' },
      { title: '限制 CAN 控制器负载', detail: '关闭非关键周期报文，目标 CAN 负载 < 65%。' },
      { title: '执行车控安全自检', detail: '覆盖锁步核、ECC、MPU 与 IO 看门狗。' }
    ],
    'vdc-io': [
      { title: '检查右后门 LIN', detail: '复核接插件、线束与节点终端电阻。' },
      { title: '复测车窗响应', detail: '执行 20 次防夹与升降循环，目标响应 < 20ms。' },
      { title: '校准座椅/后视镜', detail: '复测位置反馈与记忆功能。' }
    ],
    'vdc-network': [
      { title: '降低 CAN FD 0 负载', detail: '关闭非关键周期报文，目标 < 65%。' },
      { title: '检查 LIN 终端电阻', detail: '复核右后门节点与主节点终端匹配。' },
      { title: '抓取网关丢包统计', detail: '定位 U0100 与 CAN 高负载的时间相关性。' }
    ],
    'vdc-power': [
      { title: '复核 12V 瞬态', detail: '测量冷启动电压跌落与持续时间，确认是否触发复位。' },
      { title: '检查 DC-DC 输出', detail: '验证 13.5V 输出与纹波，目标 ±0.3V。' },
      { title: '测量静态电流', detail: '休眠 30 分钟后复测，目标 < 30mA。' }
    ],
    'vdc-diagnostics': [
      { title: '执行 UDS 全量自检', detail: '读取所有 ECU DTC 与冻结帧。' },
      { title: '复核 U0100 根因', detail: '联动 CAN 负载与 12V 瞬态分析。' },
      { title: '延后 OTA 至电源稳定', detail: '确认 12V 稳定后继续下载与安装。' }
    ],
    'vdc-stability': [
      { title: '抓取复位现场', detail: '保存 VDC watchdog、dmesg 与 12V 波形。' },
      { title: '执行 12h 掉电回归', detail: '注入 12V 跌落，目标 0 异常复位。' },
      { title: '复核启动自检', detail: '覆盖 MPU、栈保护、CRC 与安全岛。' }
    ]
  };

  const state = {
    theme: getStoredTheme() === 'light' ? 'light' : 'dark',
    view: 'overview',
    domain: 'cdc',
    activeModule: null,
    eventFilter: 'anomaly',
    ddrCapacity: '8',
    scanning: false,
    scanProgress: 0,
    scanTimer: null,
    sourceName: 'cockpit_diagnostic_20261024.log',
    sourceLogs: SAMPLE_LOG,
    parsed: { events: [], errors: [], totalLines: 0, parsedLines: 0, skipped: 0 },
    lastScan: null,
    modules: MODULE_DEFS.map((definition) => ({ ...definition, events: [] })),
    summary: null,
    globalSummary: null,
    fps: 30,
    live: createLiveState(),
    history: createHistory(),
    modalMode: null,
    pendingLogName: null
  };

  const CHART_ENTRIES = new Map();
  let lastChartFrame = 0;
  let fpsFrames = 0;
  let fpsStartedAt = performance.now();
  let chartLoopStarted = false;

  /* ============================================================
     Live data seed
     ============================================================ */

  function createLiveState() {
    return {
      soc: {
        cpuAvg: 63.2,
        gpu: 58,
        npu: 47,
        mpu: 38,
        temp: 72.4,
        power: 19.4,
        eccCe: 12,
        eccUe: 0,
        uvCount: 1,
        cores: Array.from({ length: 12 }, (_, index) => ({
          load: index === 3 ? 16 : [58, 44, 61, 16, 55, 63, 49, 72, 57, 46, 60, 52][index],
          temp: index === 3 ? 58 : 54 + (index % 4) * 3,
          freq: index === 3 ? 1.8 : index === 7 ? 2.4 : 1.8,
          voltage: index === 3 ? 0.71 : 0.82,
          warn: index === 3
        }))
      },
      ddr: {
        usage: 74.2,
        jump: 2.1,
        bandwidth: 31.4,
        capacity: '8',
        channels: [
          { usage: 78.1, bandwidth: 8.4, errors: 0 },
          { usage: 71.4, bandwidth: 7.8, errors: 0 },
          { usage: 91.2, bandwidth: 9.6, errors: 4 },
          { usage: 66.8, bandwidth: 5.6, errors: 0 }
        ]
      },
      storage: {
        usage: 78.4,
        bad: 3,
        latency: 18.2,
        read: 432,
        write: 126,
        life: 91,
        blocks: createStorageBlocks()
      },
      rf: {
        rsrp2g: -89,
        rsrp3g: -96,
        rsrp4g: -84,
        rsrp5g: -98,
        wifiRssi: -54,
        btRssi: -71,
        nearlinkRssi: -62,
        nfcRssi: -46,
        quality5g: 64,
        qualityWifi: 83,
        qualityBt: 68,
        qualityNfc: 46
      },
      audio: {
        jitter: 2.4,
        micLevels: [-32, -38, -58, -35],
        fmSignal: 62,
        amSnr: 12
      },
      peripherals: {
        camFps: 24,
        drop: 18,
        displaysOnline: 5
      },
      mcu: {
        adc4: 4.62,
        canLoad: 78,
        fanRpm: 3200,
        hbRda: 58,
        heartbeats: [
          { name: '安全岛', rate: 60, ok: true, missed: 0 },
          { name: 'RDA', rate: 58, ok: false, missed: 2 },
          { name: 'NRDA', rate: 60, ok: true, missed: 0 }
        ]
      },
      stability: {
        panic: 1,
        reboot: 2,
        anr: 3,
        crash: 1,
        uptime: 842
      },
      power: {
        total: 42.4,
        temp: 72.4,
        peak: 68.1,
        fan: 4100
      },
      mdc: {
        cpuAvg: 58,
        npu0: 72,
        npu1: 68,
        gpu: 44,
        temp: 78.2,
        power: 64.2,
        lockstep: 2,
        watchdog: 0,
        heartbeat: 60,
        ddrUsage: 66.2,
        ddrBandwidth: 48.2,
        ddrEcc: 5,
        ddrTemp: 71.4,
        ddrCh0: 68.4,
        ddrCh1: 61.2,
        ddrCh2: 78.8,
        ddrCh3: 54.6,
        ddrBw0: 11.2,
        ddrBw1: 10.4,
        ddrBw2: 14.8,
        ddrBw3: 8.6,
        storageUsage: 61.4,
        modelLatency: 128,
        storageRead: 1240,
        storageBad: 1,
        sensorLatency: 48,
        lidarDrop: 4.2,
        cameraFps: 29.2,
        ethLatency: 186,
        packetLoss: 0.8,
        ptpOffset: 1.8,
        fan: 5200
      },
      vdc: {
        cpuLoad: 42,
        safetyIsland: 60,
        ecc: 0,
        temp: 63.4,
        power: 12.8,
        heartbeat: 60,
        canLoad: 78,
        linTimeouts: 3,
        ioLatency: 8.2,
        brakePressure: 0,
        steeringAngle: 0.4,
        torque: 210,
        suspension: 2,
        voltage12: 11.82,
        quiescent: 18,
        dcDc: 13.82,
        doorFaults: 0,
        lightFaults: 0,
        actuatorFaults: 1,
        dtc: 4,
        ota: 72,
        diagReq: 24,
        resets: 1,
        faults: 2
      }
    };
  }

  function createStorageBlocks() {
    return Array.from({ length: 40 }, (_, index) => {
      let status = 'good';
      if ([2, 23, 31].includes(index)) status = 'bad';
      else if ([14, 29].includes(index)) status = 'worn';
      else if (index >= 37) status = 'reserved';
      return {
        index,
        pba: index === 2 ? '0x0000A3' : `0x${(index * 64).toString(16).padStart(4, '0').toUpperCase()}`,
        status,
        wear: status === 'bad' ? 0 : clamp(24 + index * 1.7, 18, 96)
      };
    });
  }

  function seedSeries(base, amplitude, length = 48) {
    return Array.from({ length }, (_, index) => round(base + Math.sin(index / 4.4) * amplitude + rand(-amplitude * 0.35, amplitude * 0.35), 3));
  }

  function createHistory() {
    return {
      socCpu: seedSeries(63, 6),
      socGpu: seedSeries(58, 4),
      socNpu: seedSeries(47, 5),
      ddr0: seedSeries(78, 4),
      ddr1: seedSeries(71, 4),
      ddr2: seedSeries(91, 3),
      ddr3: seedSeries(67, 4),
      stoRead: seedSeries(430, 40),
      stoWrite: seedSeries(126, 16),
      rf5g: seedSeries(64, 6),
      rfWifi: seedSeries(83, 4),
      rfBt: seedSeries(68, 5),
      rfNfc: seedSeries(46, 6),
      mic1: seedSeries(62, 5),
      mic2: seedSeries(58, 4),
      mic3: seedSeries(32, 5),
      mic4: seedSeries(60, 4),
      camFront: seedSeries(27, 2),
      camRear: seedSeries(30, 0.4),
      camDms: seedSeries(30, 0.5),
      camOms: seedSeries(29, 0.7),
      mcuAdc: seedSeries(4.6, 0.07),
      hbRda: seedSeries(58, 4),
      socPower: seedSeries(19.4, 1.2),
      socTemp: seedSeries(72.4, 1.2),
      pwr: seedSeries(43, 2.2),
      temp: seedSeries(73, 2),
      mdcCpu: seedSeries(58, 6),
      mdcNpu0: seedSeries(72, 6),
      mdcNpu1: seedSeries(68, 6),
      mdcGpu: seedSeries(44, 5),
      mdcDdr: seedSeries(66, 4),
      mdcBw: seedSeries(48, 4),
      mdcSto: seedSeries(1240, 80),
      mdcCam: seedSeries(29, 2),
      mdcLidar: seedSeries(1.2, 0.8),
      mdcEth: seedSeries(186, 18),
      mdcLoss: seedSeries(0.4, 0.2),
      mdcHeart: seedSeries(60, 2),
      mdcPwr: seedSeries(64, 4),
      mdcTemp: seedSeries(78, 2),
      vdcCpu: seedSeries(42, 4),
      vdcIo: seedSeries(8, 2),
      vdcBrake: seedSeries(0, 0.4),
      vdcSteer: seedSeries(0.4, 0.3),
      vdcCan: seedSeries(62, 5),
      vdcLin: seedSeries(1, 1),
      vdcVolt: seedSeries(11.9, 0.12),
      vdcCurr: seedSeries(18, 2),
      vdcDtc: seedSeries(4, 1),
      vdcOta: seedSeries(72, 2),
      vdcResets: seedSeries(1, 0.4)
    };
  }

  const STABILITY_HOURLY = [0, 1, 0, 2, 1, 0, 1, 2, 3, 1, 0, 2, 2, 1, 3, 2, 1, 2, 4, 2, 3, 1, 2, 3];
  state.live.stability.hourly = STABILITY_HOURLY.slice();

  /* ============================================================
     Log parser
     ============================================================ */

  function interpolate(template, fields) {
    return template.replace(/\{(\w+)\}/g, (match, key) => (fields[key] == null ? '—' : fields[key]));
  }

  function parseFieldMap(message) {
    const fields = {};
    message.replace(/([A-Za-z_][\w]*)=([^\s]+)/g, (match, key, value) => {
      fields[key] = value;
      return match;
    });
    return fields;
  }

  function severityFromLevel(level) {
    if (level === 'FATAL' || level === 'ERROR') return 'critical';
    if (level === 'WARN' || level === 'WARNING') return 'warning';
    return 'info';
  }

  function severityLabel(severity) {
    if (severity === 'critical') return '严重';
    if (severity === 'warning') return '警告';
    return '提示';
  }

  function parseDiagnosticLogs(text) {
    const lines = String(text || '').split(/\r?\n/);
    const events = [];
    const errors = [];
    let parsedLines = 0;
    let skipped = 0;

    lines.forEach((rawLine, index) => {
      const line = rawLine.trim();
      if (!line || line.startsWith('#')) return;
      const match = line.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d{1,3}))?\s+\[([A-Z0-9_]+)\]\s+\[(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\]\s*(.*)$/i);
      if (!match) {
        skipped += 1;
        if (errors.length < 6) errors.push({ line: index + 1, raw: line.slice(0, 100), reason: '格式不匹配' });
        return;
      }

      const [, date, time, millis, tag, rawLevel, message] = match;
      const level = rawLevel.toUpperCase();
      const fields = parseFieldMap(message);
      const code = (fields.code || `${tag.toUpperCase()}_${level}`).toUpperCase();
      const moduleId = CODE_TO_MODULE[code] || TAG_TO_MODULE[tag.toUpperCase()];
      if (!moduleId) {
        skipped += 1;
        if (errors.length < 6) errors.push({ line: index + 1, raw: line.slice(0, 100), reason: `未知标签 ${tag}` });
        return;
      }

      const meta = EVENT_META[code] || {};
      const severity = meta.severity || severityFromLevel(level);
      const timestamp = new Date(`${date}T${time}${millis ? `.${millis}` : ''}`).getTime();
      const chipKeys = ['core', 'ch', 'bank', 'ce', 'ue', 'pba', 'count', 'vdd', 'threshold', 'rsrp', 'antenna', 'node', 'reg', 'cam', 'fps', 'drop', 'adc', 'voltage', 'can', 'load', 'power', 'temp'];
      const chips = chipKeys
        .filter((key) => fields[key] != null)
        .slice(0, 4)
        .map((key) => `${key}=${fields[key]}`);

      parsedLines += 1;
      events.push({
        id: `evt-${index}-${code}`,
        sourceLine: index + 1,
        moduleId,
        tag: tag.toUpperCase(),
        level,
        severity,
        severityLabel: severityLabel(severity),
        code,
        title: meta.title || `${tag.toUpperCase()} ${level} 事件`,
        detail: meta.detail ? interpolate(meta.detail, fields) : message,
        fields,
        chips,
        raw: line,
        time: `${time}${millis ? `.${millis}` : ''}`,
        shortTime: time.slice(0, 5),
        date,
        timestamp
      });
    });

    return {
      events,
      errors,
      totalLines: lines.filter((line) => line.trim() && !line.trim().startsWith('#')).length,
      parsedLines,
      skipped
    };
  }

  /* ============================================================
     Scan
     ============================================================ */

  function applyParsedResult(parsed) {
    state.parsed = parsed;
    state.modules.forEach((module) => {
      module.events = parsed.events
        .filter((event) => event.moduleId === module.id)
        .sort((first, second) => second.timestamp - first.timestamp);
    });
    const ddrModel = parsed.events.find((event) => event.code === 'DDR_MODEL');
    const capacityMatch = String(ddrModel?.fields?.cap || '').match(/^(\d+)/);
    if (capacityMatch && CAPACITY_PROFILES[capacityMatch[1]]) {
      state.ddrCapacity = capacityMatch[1];
      state.live.ddr.capacity = state.ddrCapacity;
    }
    state.summary = computeSummary(state.domain);
    state.globalSummary = computeSummary(null);
    state.scanning = false;
    state.scanProgress = 100;
    state.lastScan = new Date();
  }

  function computeSummary(domain = null) {
    const scopedModules = domain ? state.modules.filter((module) => module.domain === domain) : state.modules;
    const modules = scopedModules.map((module) => getModuleState(module));
    const anomalies = modules.reduce((total, module) => total + module.critical + module.warning, 0);
    const critical = modules.reduce((total, module) => total + module.critical, 0);
    const warning = modules.reduce((total, module) => total + module.warning, 0);
    const modulesAffected = modules.filter((module) => module.critical + module.warning > 0).length;
    const health = modules.length
      ? round(modules.reduce((total, module) => total + module.health, 0) / modules.length, 1)
      : 0;
    const totalEvents = domain
      ? state.parsed.events.filter((event) => {
        const module = state.modules.find((item) => item.id === event.moduleId);
        return module?.domain === domain;
      }).length
      : state.parsed.events.length;
    const status = critical >= 2 || health < 82 ? 'critical' : anomalies > 0 ? 'warning' : 'healthy';
    return {
      domain,
      health,
      anomalies,
      critical,
      warning,
      modulesAffected,
      moduleCount: modules.length,
      totalEvents,
      logLines: state.parsed.totalLines,
      skipped: state.parsed.skipped,
      status,
      statusLabel: status === 'critical' ? '需维修 / 严重' : status === 'warning' ? '需关注 / 观察' : '健康'
    };
  }

  function getModuleState(module) {
    const events = module.events || [];
    const critical = events.filter((event) => event.severity === 'critical').length;
    const warning = events.filter((event) => event.severity === 'warning').length;
    const info = events.filter((event) => event.severity === 'info').length;
    const health = round(clamp(97.5 - critical * 5.2 - warning * 1.5 - info * 0.1, 42, 99), 1);
    const status = critical >= 2 || health < 82 ? 'critical' : critical + warning > 0 ? 'warning' : 'healthy';
    const top = events.find((event) => event.severity === 'critical')
      || events.find((event) => event.severity === 'warning')
      || events.find((event) => event.severity !== 'info')
      || events[0];
    return {
      ...module,
      events,
      critical,
      warning,
      info,
      anomalies: critical + warning,
      health,
      status,
      statusLabel: status === 'critical' ? '严重' : status === 'warning' ? '关注' : '正常',
      topEvent: top,
      summary: top
        ? `${top.title}。${top.detail}`
        : '当前模块未发现异常，日志解析与实时监控均处于正常区间。'
    };
  }

  function updateScanProgressDom() {
    const globalSummary = state.globalSummary || computeSummary(null);
    setText('#scanChipText', state.scanning ? `正在解析 ${state.scanProgress}%` : `已扫描 ${fmtInt(state.parsed.totalLines)} 行 · 3 域`);
    const scanChip = $('#scanChip');
    if (scanChip) scanChip.classList.toggle('scanning', state.scanning);
    const progressBar = $('#scanProgressBar');
    if (progressBar) progressBar.style.width = `${state.scanProgress}%`;
    setText('#scanPercent', `${state.scanProgress}%`);
    const banner = $('#scanBanner');
    if (banner) banner.classList.toggle('scanning', state.scanning);
    const bannerTitle = $('#scanBannerTitle');
    if (bannerTitle) {
      bannerTitle.textContent = state.scanning ? '正在扫描日志并映射 CDC / MDC / VDC 三域模块' : '日志扫描完成 · 三域模块已建立关联';
    }
    const bannerSub = $('#scanBannerSub');
    if (bannerSub) {
      bannerSub.textContent = state.scanning
        ? '逐行解析时间戳、标签、等级、code 与键值字段，生成异常指纹…'
        : `解析 ${fmtInt(state.parsed.totalLines)} 行，命中 ${fmtInt(state.parsed.events.length)} 条事件 / 全域 ${fmtInt(globalSummary.anomalies)} 条异常。`;
    }
  }

  function startLogScan(options = {}) {
    if (state.scanning) return;
    const announce = options.announce !== false;
    state.scanning = true;
    state.scanProgress = 0;
    renderHeaderStatus();
    renderSidebar();
    renderView();
    const started = Date.now();
    if (state.scanTimer) window.clearInterval(state.scanTimer);
    state.scanTimer = window.setInterval(() => {
      const elapsed = Date.now() - started;
      state.scanProgress = Math.min(91, Math.round((elapsed / 980) * 91));
      updateScanProgressDom();
    }, 50);

    window.setTimeout(() => {
      if (state.scanTimer) window.clearInterval(state.scanTimer);
      state.scanTimer = null;
      const parsed = parseDiagnosticLogs(state.sourceLogs);
      applyParsedResult(parsed);
      renderAll();
      if (announce) {
        toast(
          `日志扫描完成 · ${parsed.totalLines} 行 / ${parsed.events.length} 事件 / ${state.summary.anomalies} 异常`,
          parsed.errors.length ? 'warn' : 'ok'
        );
      }
    }, 1020);
  }

  /* ============================================================
     Theme / header / sidebar
     ============================================================ */

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.dataset.theme = theme;
    storeTheme(theme);
    const meta = $('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'light' ? '#EEF2F9' : '#0F0F1E');
    const toggle = $('#themeToggle');
    if (toggle) {
      toggle.setAttribute('aria-label', theme === 'light' ? '切换深色主题' : '切换白色主题');
      toggle.setAttribute('title', theme === 'light' ? '切换深色主题' : '切换白色主题');
    }
  }

  function renderHeaderStatus() {
    setText('#fpsValue', state.fps);
    updateScanProgressDom();
  }

  function renderSidebar() {
    const nav = $('#moduleNav');
    if (!nav) return;
    const domain = DOMAINS[state.domain] || DOMAINS.cdc;
    const summary = state.summary || computeSummary(state.domain);
    const globalSummary = state.globalSummary || computeSummary(null);
    const overviewActive = state.view === 'overview';
    const domainSwitch = $('#domainSwitch');
    if (domainSwitch) {
      domainSwitch.innerHTML = DOMAIN_ORDER.map((domainId) => {
        const meta = DOMAINS[domainId];
        const domainSummary = computeSummary(domainId);
        const active = state.domain === domainId;
        return `
          <button class="domain-btn ${active ? 'active' : ''}" type="button" data-domain="${domainId}" style="--accent:${meta.color};--accent-rgb:${meta.rgb}" aria-pressed="${active}">
            <span class="domain-btn-code">${meta.code}</span>
            <span class="domain-btn-copy"><b>${meta.name}</b><small>${meta.en}</small></span>
            <span class="domain-btn-health ${domainSummary.anomalies ? 'attention' : ''}">${fmt(domainSummary.health, 1)}</span>
          </button>
        `;
      }).join('') + `
          <button class="domain-btn ${state.view === 'joint' ? 'active' : ''}" type="button" data-joint="1" style="--accent:#8B5CF6;--accent-rgb:139,92,246" aria-pressed="${state.view === 'joint'}">
            <span class="domain-btn-code">ALL</span>
            <span class="domain-btn-copy"><b>三域联合诊断</b><small>JOINT DIAGNOSIS</small></span>
            <span class="domain-btn-health ${globalSummary.anomalies ? 'attention' : ''}">${fmt(globalSummary.health, 1)}</span>
          </button>
        `;
    }
    setText('#sidebarModuleMeta', `${MODULE_DEFS.length} MODULES`);
    nav.innerHTML = `
      <button class="nav-item overview ${overviewActive ? 'active' : ''}" type="button" data-view="overview" style="--accent:${domain.color};--accent-rgb:${domain.rgb}">
        <span class="nav-index">00</span>
        <span class="nav-icon">${icon('overview')}</span>
        <span class="nav-copy"><span class="nav-name">${domain.code} 域诊断总览</span><span class="nav-sub">${domain.en}</span></span>
        <span class="nav-badge ${summary.status === 'critical' ? 'critical' : summary.anomalies ? 'warning' : ''}">${summary.anomalies}</span>
      </button>
      ${state.modules.filter((module) => module.domain === state.domain).map((module) => {
        const moduleState = getModuleState(module);
        const active = state.view === 'module' && state.activeModule === module.id;
        return `
          <button class="nav-item ${active ? 'active' : ''}" type="button" data-module="${module.id}" style="--accent:${module.color};--accent-rgb:${module.rgb}" ${active ? 'aria-current="page"' : ''}>
            <span class="nav-index">${module.index}</span>
            <span class="nav-icon">${icon(module.icon)}</span>
            <span class="nav-copy"><span class="nav-name">${module.name}</span><span class="nav-sub">${module.en}</span></span>
            <span class="nav-badge ${moduleState.status === 'critical' ? 'critical' : moduleState.anomalies ? 'warning' : ''}">${moduleState.anomalies}</span>
          </button>
        `;
      }).join('')}
    `;

    const source = $('#sidebarSource');
    if (!source) return;
    source.innerHTML = `
      <div class="source-head">${icon('file')}日志源 <span class="live-dot" style="margin-left:auto"></span></div>
      <div class="source-file" title="${escapeHtml(state.sourceName)}">${escapeHtml(state.sourceName)}</div>
      <div class="source-grid">
        <div class="source-stat"><span>日志行</span><b>${fmtInt(globalSummary.logLines)}</b></div>
        <div class="source-stat"><span>全域异常</span><b>${globalSummary.anomalies}</b></div>
        <div class="source-stat"><span>命中模块</span><b>${globalSummary.modulesAffected} / ${globalSummary.moduleCount}</b></div>
        <div class="source-stat"><span>在线域</span><b>3 / 3</b></div>
      </div>
      <button class="source-action" type="button" data-action="import-log">${icon('upload')}导入新的日志文件</button>
    `;
  }

  function toast(message, type = 'ok') {
    const stack = $('#toastRoot');
    if (!stack) return;
    const element = document.createElement('div');
    element.className = `toast ${type}`;
    element.innerHTML = `${icon(type === 'ok' ? 'check' : type === 'warn' ? 'alert' : 'close')}<span>${escapeHtml(message)}</span>`;
    stack.appendChild(element);
    window.setTimeout(() => {
      element.classList.add('leaving');
      window.setTimeout(() => element.remove(), 220);
    }, 3600);
  }

  /* ============================================================
     Overview
     ============================================================ */

  function renderAll() {
    state.globalSummary = computeSummary(null);
    state.summary = computeSummary(state.domain);
    renderHeaderStatus();
    renderSidebar();
    renderView();
  }

  function renderView() {
    if (state.view === 'joint') {
      renderJointOverview();
    } else if (state.view === 'module' && state.activeModule) {
      renderModuleDetail();
    } else {
      renderOverview();
    }
    mountCharts();
    updateLiveLabels();
    if (state.view === 'module' && state.activeModule === 'soc') updateCoreDom();
    window.requestAnimationFrame(() => {
      updateLiveLabels();
      if (state.view === 'module' && state.activeModule === 'soc') updateCoreDom();
    });
  }

  function modelStatusPill(moduleState) {
    return `<span class="status-pill ${moduleState.status}">${moduleState.statusLabel}</span>`;
  }

  function scanBannerHTML() {
    const summary = state.summary || computeSummary(state.domain);
    const globalSummary = state.globalSummary || computeSummary(null);
    const domain = DOMAINS[state.domain] || DOMAINS.cdc;
    return `
      <div class="scan-banner ${state.scanning ? 'scanning' : ''}" id="scanBanner">
        <div class="scan-icon">${icon('scan')}</div>
        <div class="scan-copy">
          <b id="scanBannerTitle">${state.scanning ? '正在扫描日志并映射 CDC / MDC / VDC 三域模块' : '日志扫描完成 · 三域模块已建立关联'}</b>
          <span id="scanBannerSub">${state.scanning ? '逐行解析时间戳、标签、等级、code 与键值字段，生成异常指纹…' : `解析 ${fmtInt(state.parsed.totalLines)} 行，命中 ${fmtInt(state.parsed.events.length)} 条事件 / 全域 ${globalSummary.anomalies} 条异常 / 当前 ${domain.code} ${summary.anomalies} 条。`}</span>
        </div>
        <div class="scan-progress">
          <div class="scan-progress-head"><span>${state.scanning ? '正在解析' : '解析完成'}</span><b id="scanPercent">${state.scanProgress}%</b></div>
          <div class="scan-progress-track"><i id="scanProgressBar" style="width:${state.scanProgress}%"></i></div>
        </div>
        <div class="scan-stats">
          <div class="scan-stat"><span>模块</span><b>${summary.modulesAffected} / ${summary.moduleCount}</b></div>
          <div class="scan-stat"><span>严重</span><b class="critical">${summary.critical}</b></div>
          <div class="scan-stat"><span>警告</span><b class="warning">${summary.warning}</b></div>
          <div class="scan-stat"><span>全域异常</span><b>${globalSummary.anomalies}</b></div>
        </div>
      </div>
    `;
  }

  function kpiHTML() {
    const domain = DOMAINS[state.domain] || DOMAINS.cdc;
    const domainModules = state.modules.filter((module) => module.domain === state.domain);
    const summary = state.summary || computeSummary(state.domain);
    const globalSummary = state.globalSummary || computeSummary(null);
    const healthWidth = clamp(summary.health, 0, 100);
    const anomalyWidth = clamp(summary.anomalies * 3, 0, 100);
    const parseWidth = state.parsed.totalLines ? clamp((state.parsed.parsedLines / state.parsed.totalLines) * 100, 0, 100) : 0;
    return `
      <div class="kpi-grid">
        <article class="kpi-card" style="--k:${domain.color};--k-rgb:${domain.rgb}">
          <div class="kpi-top"><span class="kpi-icon">${icon('activity')}</span><span class="kpi-label">${domain.code} 综合健康度</span></div>
          <div class="kpi-value"><b>${fmt(summary.health, 1)}</b><span>/ 100</span></div>
          <div class="kpi-sub">${summary.modulesAffected} / ${summary.moduleCount} 模块受影响 · ${summary.statusLabel}</div>
          <div class="kpi-bar"><i style="width:${healthWidth}%"></i></div>
        </article>
        <article class="kpi-card" style="--k:#FB7185;--k-rgb:251,113,133">
          <div class="kpi-top"><span class="kpi-icon">${icon('alert')}</span><span class="kpi-label">${domain.code} 异常事件</span></div>
          <div class="kpi-value"><b>${summary.anomalies}</b><span>条</span></div>
          <div class="kpi-sub">严重 ${summary.critical} · 警告 ${summary.warning}</div>
          <div class="kpi-bar"><i style="width:${anomalyWidth}%"></i></div>
        </article>
        <article class="kpi-card" style="--k:#22D3EE;--k-rgb:34,211,238">
          <div class="kpi-top"><span class="kpi-icon">${icon('file')}</span><span class="kpi-label">三域日志解析</span></div>
          <div class="kpi-value"><b>${fmtInt(globalSummary.logLines)}</b><span>行</span></div>
          <div class="kpi-sub">命中 ${fmtInt(state.parsed.events.length)} 条 · 全域 ${globalSummary.anomalies} 异常</div>
          <div class="kpi-bar"><i style="width:${parseWidth}%"></i></div>
        </article>
        <article class="kpi-card" style="--k:#A3E635;--k-rgb:163,230,53">
          <div class="kpi-top"><span class="kpi-icon">${icon('gauge')}</span><span class="kpi-label">实时渲染帧率</span></div>
          <div class="kpi-value"><b id="kpiFpsValue">${state.fps >= 12 ? 30 : state.fps}</b><span>FPS</span></div>
          <div class="kpi-sub">${domainModules.length} 模块动态绘图 · 稳定输出</div>
          <div class="kpi-bar"><i style="width:${clamp(state.fps / 30 * 100, 0, 100)}%"></i></div>
        </article>
      </div>
    `;
  }

  function moduleCardHTML(module) {
    const moduleState = getModuleState(module);
    const latest = (moduleState.events.filter((event) => event.severity !== 'info')).slice(0, 3);
    const fallback = latest.length ? latest : moduleState.events.slice(0, 3);
    const timeline = state.scanning
      ? `<div class="mini-empty">正在解析日志并生成异常时间轴…</div>`
      : fallback.length
        ? fallback.map((event) => `
            <div class="mini-event ${event.severity}">
              <span class="mini-dot"></span>
              <div class="mini-event-copy">
                <span class="mini-event-title"><span class="mini-event-time">${event.shortTime}</span>${escapeHtml(event.title)}</span>
              </div>
            </div>
          `).join('')
        : `<div class="mini-empty">该模块未发现异常事件</div>`;

    const metrics = module.cardMetrics.map((metric) => {
      const spec = metric.source || metric.threshold
        ? `<small class="metric-spec">${metric.source ? escapeHtml(metric.source) : ''}${metric.source && metric.threshold ? ' · ' : ''}${metric.threshold ? escapeHtml(metric.threshold) : ''}</small>`
        : '';
      if (metric.value) {
        return `<div class="module-metric"><span>${metric.label}</span><b>${metric.value}<em>${metric.unit || ''}</em></b>${spec}</div>`;
      }
      const current = getPath(state.live, metric.live);
      const display = current == null ? '--' : Number(current).toFixed(metric.digits || 0);
      return `<div class="module-metric"><span>${metric.label}</span><b><span data-live="${metric.live}" data-digits="${metric.digits}">${display}</span><em>${metric.unit || ''}</em></b>${spec}</div>`;
    }).join('');

    return `
      <article class="module-card" style="--accent:${module.color};--accent-rgb:${module.rgb}" data-open-module="${module.id}">
        <div class="module-top">
          <div class="module-icon">${icon(module.icon)}</div>
          <div class="module-title-wrap">
            <div class="module-code">${module.index} · ${module.en}</div>
            <div class="module-title">${module.name}</div>
            <div class="module-en">${module.subtitle}</div>
          </div>
          <div class="module-health">
            <span class="health-score">${fmt(moduleState.health, 1)}<span>/100</span></span>
            ${modelStatusPill(moduleState)}
          </div>
        </div>
        <div class="module-metrics">${metrics}</div>
        <div class="module-section">
          <div class="module-section-head">
            <span class="module-section-label">${icon('timeline')}异常事件时间轴</span>
            <span class="module-section-count">${moduleState.anomalies}</span>
          </div>
          <div class="mini-timeline">${timeline}</div>
        </div>
        <div class="module-chart">
          <div class="chart-topline"><span>${module.chartCaption}</span><span class="chart-live"><i></i>LIVE</span></div>
          <div class="mini-chart"><canvas data-mini="${module.id}" aria-label="${module.name} 实时监控"></canvas></div>
        </div>
        <div class="module-foot">
          <span class="module-foot-meta">日志 ${moduleState.events.length} 条 · 解析命中 ${moduleState.anomalies}</span>
          <button class="module-link" type="button" data-open-module="${module.id}">展开诊断${icon('arrow-right')}</button>
        </div>
      </article>
    `;
  }

  function renderOverview() {
    const main = $('#mainContent');
    if (!main) return;
    const domain = DOMAINS[state.domain] || DOMAINS.cdc;
    const domainModules = state.modules.filter((module) => module.domain === state.domain);
    const summary = state.summary || computeSummary(state.domain);
    const globalSummary = state.globalSummary || computeSummary(null);
    main.innerHTML = `
      <div class="page-head">
        <div>
          <span class="eyebrow">${domain.code} · ${domain.en} DIAGNOSTIC WORKSPACE</span>
          <h1>${domain.name}诊断总览</h1>
          <p class="page-sub">三域统一日志扫描 · ${domainModules.length} 个专属模块异常时间轴 · 实时监控联动 · 一键生成 8D 维修报告</p>
        </div>
        <div class="page-head-actions">
          <span class="page-meta">${icon('activity')}${state.lastScan ? `上次扫描 ${formatTime(state.lastScan)}` : '等待首次扫描'}</span>
          <span class="page-meta">${icon('layers')}${domainModules.length} 个模块</span>
          <span class="page-meta">${icon('cpu')}全域 ${globalSummary.moduleCount} 个模块</span>
        </div>
      </div>
      ${scanBannerHTML()}
      ${kpiHTML()}
      <div class="module-grid">
        ${domainModules.map(moduleCardHTML).join('')}
      </div>
      <footer class="page-footer" style="margin-top:22px;padding-top:14px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:14px;color:var(--text-3);font-size:8px">
        <span>NEXUS COCKPIT · 日志解析器 v2.4 · CDC / MDC / VDC 三域联合诊断 · ${summary.logLines} 行日志</span>
        <span>DEMO DATA · 模拟车载日志与实时遥测，不作为真实维修依据</span>
      </footer>
    `;
  }

  /* ============================================================
     Timeline
     ============================================================ */

  function filterEvents(events, filter) {
    if (filter === 'all') return events;
    if (filter === 'anomaly') return events.filter((event) => event.severity === 'critical' || event.severity === 'warning');
    return events.filter((event) => event.severity === filter);
  }

  function timelineItemsHTML(moduleState) {
    const events = filterEvents(moduleState.events, state.eventFilter);
    if (!events.length) {
      return `<div class="timeline-empty">当前筛选条件下没有异常事件。<br>日志解析完成后，时间轴会自动填充。</div>`;
    }
    return events.map((event) => `
      <article class="timeline-event ${event.severity}">
        <div class="event-time"><b>${event.time.slice(0, 8)}</b><span>${event.date.slice(5)}</span></div>
        <div class="event-body">
          <div class="event-meta">
            <span class="severity-badge ${event.severity}">${event.severityLabel}</span>
            <span class="source-tag">[${event.tag}]</span>
            <span class="source-tag">LINE ${event.sourceLine}</span>
          </div>
          <h4 class="event-title">${escapeHtml(event.title)}</h4>
          <p class="event-desc">${escapeHtml(event.detail)}</p>
          ${event.chips.length ? `<div class="event-fields">${event.chips.map((chip) => `<span class="field-chip">${escapeHtml(chip)}</span>`).join('')}</div>` : ''}
        </div>
      </article>
    `).join('');
  }

  function filterToolbarHTML() {
    const filters = [
      { id: 'anomaly', label: '异常' },
      { id: 'critical', label: '严重' },
      { id: 'warning', label: '警告' },
      { id: 'info', label: '提示' },
      { id: 'all', label: '全部' }
    ];
    return `
      <div class="event-filters">
        ${filters.map((filter) => `<button class="filter-chip ${state.eventFilter === filter.id ? 'active' : ''}" type="button" data-event-filter="${filter.id}">${filter.label}</button>`).join('')}
      </div>
    `;
  }

  function renderTimelineOnly() {
    const module = state.modules.find((item) => item.id === state.activeModule);
    if (!module) return;
    const moduleState = getModuleState(module);
    const list = $('#timelineList');
    if (list) list.innerHTML = timelineItemsHTML(moduleState);
    $$('[data-event-filter]').forEach((button) => {
      button.classList.toggle('active', button.dataset.eventFilter === state.eventFilter);
    });
  }

  /* ============================================================
     Detail view
     ============================================================ */

  function renderModuleDetail() {
    const main = $('#mainContent');
    const module = state.modules.find((item) => item.id === state.activeModule);
    if (!main || !module) {
      state.view = 'overview';
      state.activeModule = null;
      renderOverview();
      return;
    }
    const moduleState = getModuleState(module);
    state.domain = module.domain;
    const domain = DOMAINS[state.domain] || DOMAINS.cdc;
    main.innerHTML = `
      <button class="detail-back" type="button" data-view="overview">${icon('arrow-left')}返回 ${domain.code} 域诊断总览</button>
      <section class="detail-hero" style="--accent:${module.color};--accent-rgb:${module.rgb}">
        <div class="detail-hero-icon">${icon(module.icon)}</div>
        <div class="detail-title">
          <span class="eyebrow">${domain.code} · MODULE ${module.index} · ${module.en}</span>
          <h1>${module.name}</h1>
          <p>${module.subtitle}</p>
          <p class="detail-summary">${escapeHtml(moduleState.summary)}</p>
        </div>
        <div class="hero-stats">
          <div class="hero-stat"><span>健康度</span><b>${fmt(moduleState.health, 1)}</b></div>
          <div class="hero-stat"><span>异常事件</span><b>${moduleState.anomalies}</b></div>
          <div class="hero-stat"><span>严重</span><b>${moduleState.critical}</b></div>
          <div class="hero-stat"><span>警告</span><b>${moduleState.warning}</b></div>
          <div class="hero-health"><b>${fmt(moduleState.health, 1)}</b><span>HEALTH<br>INDEX</span></div>
        </div>
      </section>
      <div class="detail-grid">
        <aside class="panel timeline-panel">
          <div class="panel-head">
            <div class="panel-title">${icon('timeline')}<h2>异常事件时间轴</h2><small>${moduleState.events.length} 条日志事件</small></div>
            <span class="panel-chip live">LOG SCAN</span>
          </div>
          <div class="timeline-toolbar">${filterToolbarHTML()}<span class="panel-chip">${moduleState.anomalies} 异常</span></div>
          <div class="timeline-list" id="timelineList">${timelineItemsHTML(moduleState)}</div>
        </aside>
        <div class="detail-content" style="--accent:${module.color};--accent-rgb:${module.rgb}">
          ${moduleDetailTemplate(moduleState)}
        </div>
      </div>
    `;
  }

  /* ============================================================
     Detail templates
     ============================================================ */

  function liveSpan(key, digits = 0) {
    const value = getPath(state.live, key);
    const display = value == null ? '--' : Number(value).toFixed(digits);
    return `<span data-live="${key}" data-digits="${digits}">${display}</span>`;
  }

  function panelHTML(title, iconName, body, options = {}) {
    const classes = ['panel'];
    if (options.span2) classes.push('span-2');
    if (options.className) classes.push(options.className);
    return `
      <section class="${classes.join(' ')}">
        <div class="panel-head">
          <div class="panel-title">${icon(iconName)}<h2>${title}</h2>${options.sub ? `<small>${options.sub}</small>` : ''}</div>
          ${options.chip || ''}
        </div>
        <div class="panel-body">${body}</div>
      </section>
    `;
  }

  function coreGridHTML() {
    return state.live.soc.cores.map((core, index) => `
      <div class="core-card ${core.warn ? 'warn' : ''}" data-core="${index}">
        <div class="core-head"><span>C${pad2(index)}</span><b data-core-load="${index}">${fmt(core.load, 0)}%</b></div>
        <div class="core-bar"><i data-core-bar="${index}" style="width:${core.load}%"></i></div>
        <div class="core-meta"><span data-core-temp="${index}">${fmt(core.temp, 0)}°C</span><span data-core-freq="${index}">${fmt(core.freq, 2)}GHz</span></div>
      </div>
    `).join('');
  }

  function socDetailTemplate() {
    const gpuRows = [
      { name: 'GPU', live: 'soc.gpu', temp: 'soc.gpuTemp', tempValue: '67°C', freq: '800 MHz', status: 'healthy' },
      { name: 'NPU', live: 'soc.npu', temp: 'soc.npuTemp', tempValue: '81°C', freq: '1.0 GHz', status: 'warning' },
      { name: 'MPU', live: 'soc.mpu', temp: 'soc.mpuTemp', tempValue: '64°C', freq: '1.2 GHz', status: 'healthy' }
    ];
    const cores = panelHTML('12 核 CPU 实时负载', 'cpu', `
      <div class="core-grid">${coreGridHTML()}</div>
      <div class="soc-stat-grid" style="margin-top:8px">
        <div class="soc-stat warn"><span>最低 VDD</span><b>0.71 V</b></div>
        <div class="soc-stat"><span>ECC CE 计数</span><b>${liveSpan('soc.eccCe', 0)}</b></div>
        <div class="soc-stat"><span>ECC UE 计数</span><b>${liveSpan('soc.eccUe', 0)}</b></div>
        <div class="soc-stat"><span>频率跳变次数</span><b>3</b></div>
      </div>
    `, { span2: true, sub: '12 CORES · LIVE', chip: '<span class="panel-chip live">30 FPS</span>' });

    const gpu = panelHTML('GPU / NPU / MPU 资源表', 'layers', `
      <table class="data-table">
        <thead><tr><th>单元</th><th>占用率</th><th>温度</th><th>频率</th><th>状态</th></tr></thead>
        <tbody>
          ${gpuRows.map((row) => `
            <tr>
              <td class="strong">${row.name}</td>
              <td><div class="mini-progress"><div class="mini-progress-track"><i data-live-width="${row.live}" style="width:0%"></i></div><b>${liveSpan(row.live, 0)}%</b></div></td>
              <td class="mono">${row.tempValue}</td>
              <td class="mono">${row.freq}</td>
              <td><span class="status-pill ${row.status}">${row.status === 'healthy' ? '正常' : '关注'}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `, { sub: 'GPU · NPU · MPU' });

    const power = panelHTML('封装功率与温度', 'zap', `
      <div class="chart-canvas"><canvas data-chart="socPower" aria-label="SoC 功率与温度曲线"></canvas></div>
      <div class="chart-legend"><span class="legend-item"><i style="--legend:#4C8DFF"></i>PACKAGE POWER (W)</span><span class="legend-item"><i style="--legend:#FB7185"></i>JUNCTION TEMP (°C)</span></div>
    `, { sub: 'PACKAGE MONITOR', chip: '<span class="panel-chip live">LIVE</span>' });

    return `<div class="detail-panels">${cores}${gpu}${power}</div>`;
  }

  function ddrDetailTemplate() {
    const profile = CAPACITY_PROFILES[state.ddrCapacity];
    const channels = state.live.ddr.channels;
    return `
      <div class="detail-panels">
        ${panelHTML('4-CH 内存逻辑映射', 'memory', `
          <div class="capacity-select">
            ${Object.keys(CAPACITY_PROFILES).map((size) => `<button class="capacity-btn ${state.ddrCapacity === size ? 'active' : ''}" type="button" data-capacity="${size}">${size} GB</button>`).join('')}
          </div>
          <div class="ddr-model"><span>识别型号</span><b>${profile.model}</b><span>${profile.label} · ${profile.channels} CH × ${profile.banks} BANK · ${profile.width} · ${profile.rank} · ${profile.speed}</span></div>
          <div class="channel-grid">
            ${channels.map((channel, index) => `
              <div class="channel-card ${index === 2 ? 'warn' : ''}">
                <div class="channel-head"><span>CH${index} · ${state.ddrCapacity}GB</span><b>${liveSpan(`ddr.channels.${index}.usage`, 1)}%</b></div>
                <div class="bank-grid">
                  ${Array.from({ length: profile.banks }, (_, bank) => {
                    const warn = index === 2 && bank === 7;
                    const minor = index === 0 && bank === 3;
                    return `<span class="bank-cell ${warn ? 'bad' : minor ? 'warn' : ''}" title="CH${index} / BANK${bank} · ${fmt(channel.usage + rand(-2, 2), 1)}%">${bank}</span>`;
                  }).join('')}
                </div>
              </div>
            `).join('')}
          </div>
          <div class="parser-map">
            <div class="parser-map-head"><span>${icon('file')} 真实日志解析器映射</span><b>DDR PARSER v2.4</b></div>
            <pre class="parser-code">CAPACITY=${state.ddrCapacity}G -> ${profile.model} / ${profile.channels} CH / ${profile.banks} BANK
CH = (addr >> 8) & 0x3    BA = (addr >> 4) & 0x${(profile.banks - 1).toString(16).toUpperCase()}
LATEST: ${escapeHtml((state.modules.find((item) => item.id === 'ddr')?.events.find((event) => event.tag === 'DDR')?.raw || '等待 DDR 日志…'))}</pre>
          </div>
        `, { span2: true, sub: `LOG → CHANNEL / BANK MAPPING`, chip: '<span class="panel-chip live">PARSER CONNECTED</span>' })}
        ${panelHTML('通道占用率对比', 'activity', `
          <div class="chart-canvas"><canvas data-chart="ddrChannels" aria-label="DDR 四通道占用率"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#A855F7"></i>CH0</span><span class="legend-item"><i style="--legend:#4C8DFF"></i>CH1</span><span class="legend-item"><i style="--legend:#FB7185"></i>CH2</span><span class="legend-item"><i style="--legend:#22D3EE"></i>CH3</span></div>
        `, { sub: '4 CHANNEL OCCUPANCY' })}
        ${panelHTML('BANK 错误与跳变明细', 'layers', `
          <table class="data-table">
            <thead><tr><th>通道</th><th>占用</th><th>带宽</th><th>错误</th><th>状态</th></tr></thead>
            <tbody>${channels.map((channel, index) => `
              <tr>
                <td class="strong">CH${index}</td>
                <td class="mono">${liveSpan(`ddr.channels.${index}.usage`, 1)}%</td>
                <td class="mono">${liveSpan(`ddr.channels.${index}.bandwidth`, 1)} GB/s</td>
                <td class="mono">${channel.errors}</td>
                <td><span class="status-pill ${index === 2 ? 'warning' : 'healthy'}">${index === 2 ? '关注' : '正常'}</span></td>
              </tr>
            `).join('')}</tbody>
          </table>
        `, { sub: 'BANK / ECC DETAILS' })}
      </div>
    `;
  }

  function storageDetailTemplate() {
    const blocks = state.live.storage.blocks;
    return `
      <div class="detail-panels">
        ${panelHTML('UFS 40 物理块图谱', 'storage', `
          <div class="ufs-map">
            ${blocks.map((block) => `<span class="ufs-block ${block.status}" title="PBA ${block.pba} · ${block.status} · WEAR ${block.wear}%"><b>${pad2(block.index)}</b><span>${block.pba.slice(-4)}</span></span>`).join('')}
          </div>
          <div class="map-legend"><span><i></i>Good</span><span><i class="worn"></i>Worn</span><span><i class="bad"></i>Bad Block</span><span><i class="reserved"></i>Reserved</span><span style="margin-left:auto">PHYSICAL BLOCK MAP · 40 BLOCKS</span></div>
        `, { span2: true, sub: 'UFS 3.1 · LOGICAL TO PHYSICAL', chip: '<span class="panel-chip live">SCAN OK</span>' })}
        ${panelHTML('读写吞吐与延迟', 'activity', `
          <div class="chart-canvas"><canvas data-chart="storageIO" aria-label="UFS 读写吞吐"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#22D3EE"></i>READ MB/s</span><span class="legend-item"><i style="--legend:#A3E635"></i>WRITE MB/s</span></div>
        `, { sub: 'IO THROUGHPUT' })}
        ${panelHTML('坏块与重映射', 'alert', `
          <table class="data-table">
            <thead><tr><th>PBA</th><th>状态</th><th>磨损</th><th>处理</th></tr></thead>
            <tbody>
              <tr><td class="mono">0x0000A3</td><td><span class="status-pill critical">坏块</span></td><td class="mono">87%</td><td>已重映射 #12</td></tr>
              <tr><td class="mono">0x0005C0</td><td><span class="status-pill warning">待复核</span></td><td class="mono">72%</td><td>待迁移</td></tr>
              <tr><td class="mono">0x0007C0</td><td><span class="status-pill warning">待复核</span></td><td class="mono">68%</td><td>预留块可用</td></tr>
            </tbody>
          </table>
          <div class="soc-stat-grid" style="margin-top:8px">
            <div class="soc-stat"><span>寿命余量</span><b>${liveSpan('storage.life', 0)}%</b></div>
            <div class="soc-stat"><span>坏块</span><b>${liveSpan('storage.bad', 0)}</b></div>
            <div class="soc-stat warn"><span>P99 延迟</span><b>112 ms</b></div>
            <div class="soc-stat"><span>占用率</span><b>${liveSpan('storage.usage', 1)}%</b></div>
          </div>
        `, { sub: 'BAD BLOCK MANAGEMENT' })}
      </div>
    `;
  }

  function signalBarsHTML(quality) {
    const lit = Math.round(clamp(quality, 0, 100) / 20);
    return `<span class="bars">${Array.from({ length: 5 }, (_, index) => `<i class="${index < lit ? 'on' : ''}" style="height:${4 + index * 2}px"></i>`).join('')}</span>`;
  }

  function rfDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('全射频状态', 'radio', `
          <div class="rf-radio-list">
            ${RF_RADIOS.map((radio) => `
              <div class="rf-radio ${radio.enabled ? 'active' : ''}" style="--accent:${radio.enabled ? '#F59E0B' : '#6C7A93'}">
                <div class="rf-name"><i class="${radio.enabled ? '' : 'off'}"></i>${radio.name}</div>
                <span class="rf-band">${radio.band}</span>
                <div class="rf-signal"><div class="signal-bar">${signalBarsHTML(radio.quality)}<span class="rf-value">${liveSpan(radio.live, 0)} dBm</span></div></div>
                <span class="rf-value">${radio.quality}%</span>
                <span class="rf-state">${radio.state}</span>
              </div>
            `).join('')}
          </div>
        `, { span2: true, sub: '2G / 3G / 4G / 5G / WiFi / BT / NFC · ALL RADIOS', chip: '<span class="panel-chip live">ALL ONLINE</span>' })}
        ${panelHTML('信号强度实时示波器', 'activity', `
          <div class="chart-canvas"><canvas data-chart="rfScope" aria-label="射频信号强度示波器"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#F59E0B"></i>5G</span><span class="legend-item"><i style="--legend:#4C8DFF"></i>WiFi</span><span class="legend-item"><i style="--legend:#EC4899"></i>BT</span><span class="legend-item"><i style="--legend:#22D3EE"></i>NFC</span></div>
        `, { sub: 'QUALITY / 0 - 100' })}
        ${panelHTML('频段状态位图', 'layers', `
          <div class="band-map">
            ${RF_BANDS.map((band) => `<span class="band-chip ${band.on ? 'on' : ''}">${band.label}<i></i></span>`).join('')}
          </div>
        `, { sub: 'BAND BITMAP' })}
        ${panelHTML('天线连通性自检', 'wifi', `
          <div class="antenna-list">
            ${ANTENNAS.map((antenna) => `<div class="antenna-item ${antenna.warn ? 'warn' : ''}"><span>${antenna.name}</span><b>${antenna.resistance}</b><em>${antenna.status}</em></div>`).join('')}
          </div>
        `, { sub: 'CONTINUITY / VSWR', span2: true })}
      </div>
    `;
  }

  function audioDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('A2B 音频总线节点', 'audio', `
          <div class="a2b-topology">
            ${A2B_NODES.map((node, index) => `
              ${index > 0 ? '<span class="a2b-link"></span>' : ''}
              <div class="a2b-node ${node.status === 'warn' ? 'warn' : ''}">
                <span>${node.addr} · ${node.role}</span>
                <b>${node.name}</b>
                <span>${node.latency}</span>
              </div>
            `).join('')}
          </div>
          <table class="data-table register-table" style="margin-top:8px">
            <thead><tr><th>节点</th><th>寄存器</th><th>当前值</th><th>期望值</th><th>状态</th></tr></thead>
            <tbody>${A2B_REGISTERS.map((register) => `
              <tr><td>${register.node}</td><td>${register.reg}</td><td>${register.value}</td><td>${register.expected}</td><td><span class="status-pill ${register.status === 'warn' ? 'warning' : 'healthy'}">${register.status === 'warn' ? '异常' : '正常'}</span></td></tr>
            `).join('')}</tbody>
          </table>
        `, { span2: true, sub: '4 NODES · REGISTER HEALTH', chip: '<span class="panel-chip">CRC 7</span>' })}
        ${panelHTML('FM / AM 检测', 'radio', `
          <div class="radio-cards">
            <div class="radio-card"><div class="radio-card-head"><span>FM 调频</span><b>98.7 MHz</b></div><div class="radio-card-meta"><span>信号 ${liveSpan('audio.fmSignal', 0)} dBμV</span><span>STEREO</span><span>RDS ON</span></div></div>
            <div class="radio-card"><div class="radio-card-head"><span>AM 调幅</span><b>990 kHz</b></div><div class="radio-card-meta"><span>SNR ${liveSpan('audio.amSnr', 0)} dB</span><span>MONO</span><span>弱信号</span></div></div>
          </div>
          <div class="parser-map" style="margin-top:8px"><div class="parser-map-head"><span>TUNER STATUS</span><b>FM LOCKED / AM WARN</b></div><pre class="parser-code">FM  98.7MHz  RDS=1  SNR=42dB  OK
AM 990.0kHz  RDS=0  SNR=12dB  WARN
A2B CRC=7  NODE=3  REG=0x2C</pre></div>
        `, { sub: 'TUNER + A2B' })}
        ${panelHTML('MIC 阵列检测', 'audio', `
          <div class="mic-grid">
            ${state.live.audio.micLevels.map((level, index) => `
              <div class="mic-card ${index === 2 ? 'warn' : ''}">
                <div class="mic-head"><span>MIC${index + 1}</span><b>${liveSpan(`audio.micLevels.${index}`, 0)} dB</b></div>
                <div class="mic-meter"><i style="width:${clamp(100 + level, 8, 100)}%"></i></div>
              </div>
            `).join('')}
          </div>
          <div class="chart-canvas" style="height:110px;margin-top:6px"><canvas data-chart="audioLevels" aria-label="MIC 电平曲线"></canvas></div>
        `, { sub: 'MIC ARRAY LEVEL', span2: true })}
      </div>
    `;
  }

  function displayDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('显示屏 SerDes 链路', 'layers', `
          <div class="table-scroll"><table class="data-table" style="min-width:560px">
            <thead><tr><th>屏幕</th><th>分辨率</th><th>加串器 / 解串器</th><th>SoC 接口</th><th>Link</th><th>温度</th><th>状态</th></tr></thead>
            <tbody>${DISPLAYS.map((display) => `
              <tr>
                <td class="strong">${display.name}<br><span class="muted" style="font-family:var(--font-mono);font-size:6px">${display.size}</span></td>
                <td class="mono">${display.resolution}</td>
                <td><span class="serdes-badge">${display.serdes}</span></td>
                <td class="mono">${display.iface}</td>
                <td class="mono">${display.link}</td>
                <td class="mono">${display.temperature}°C</td>
                <td><span class="status-pill ${display.status === 'warn' ? 'warning' : 'healthy'}">${display.status === 'warn' ? '关注' : '正常'}</span></td>
              </tr>
            `).join('')}</tbody>
          </table></div>
        `, { span2: true, sub: 'TI DS90UB981 / DS90UB983 · FPD-LINK IV' })}
      </div>
    `;
  }

  function peripheralsDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('Camera 实时链路', 'monitor', `
          <table class="data-table">
            <thead><tr><th>摄像头</th><th>分辨率</th><th>FPS</th><th>丢帧</th><th>链路</th><th>状态</th></tr></thead>
            <tbody>${CAMERAS.map((camera) => `
              <tr><td class="strong">${camera.name}</td><td class="mono">${camera.resolution}</td><td class="mono">${camera.fps} / ${camera.target}</td><td class="mono">${camera.drop}</td><td class="mono">${camera.link}</td><td><span class="status-pill ${camera.status === 'warn' ? 'warning' : 'healthy'}">${camera.status === 'warn' ? '掉帧' : '正常'}</span></td></tr>
            `).join('')}</tbody>
          </table>
        `, { span2: true, sub: 'FRONT / REAR / DMS / OMS', chip: '<span class="panel-chip live">FPS MONITOR</span>' })}
        ${panelHTML('摄像头帧率曲线', 'activity', `
          <div class="chart-canvas"><canvas data-chart="periphFps" aria-label="摄像头帧率曲线"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#34D399"></i>FRONT</span><span class="legend-item"><i style="--legend:#22D3EE"></i>REAR</span><span class="legend-item"><i style="--legend:#A855F7"></i>DMS</span><span class="legend-item"><i style="--legend:#F59E0B"></i>OMS</span></div>
        `, { sub: 'FPS / DROPPED FRAMES' })}
        ${panelHTML('USB 外设', 'chip', `
          <div class="usb-list">
            ${USB_PORTS.map((port) => `<div class="usb-item"><div><b>${port.name}</b><br><span>${port.speed}</span></div><div style="text-align:right"><b>${port.power}</b><br><span>${port.device}</span></div></div>`).join('')}
          </div>
        `, { sub: 'USB 3.2 / PD' })}
      </div>
    `;
  }

  function mcuDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('ADC 采样通道', 'chip', `
          <div class="adc-grid">
            ${MCU_ADC_CHANNELS.map((channel, index) => `
              <div class="adc-card ${channel.warn ? 'warn' : ''}">
                <div class="adc-head"><span>${channel.name}</span><span>${channel.unit}</span></div>
                <div class="adc-value">${ADC_LIVE_KEYS[index] ? `${liveSpan(ADC_LIVE_KEYS[index], 2)} ${channel.unit}` : `${fmt(channel.value, 2)} ${channel.unit}`}</div>
                <div class="adc-bar"><i style="width:${clamp(channel.value / (channel.threshold * 1.2) * 100, 8, 100)}%"></i></div>
              </div>
            `).join('')}
          </div>
        `, { span2: true, sub: '8 CHANNELS · 12-BIT ADC', chip: '<span class="panel-chip">CH4 OVER LIMIT</span>' })}
        ${panelHTML('SoC 建联与三核心跳', 'cpu', `
          <div class="link-grid">
            ${state.live.mcu.heartbeats.map((heartbeat) => `
              <div class="link-card ${heartbeat.ok ? '' : 'warn'}">
                <div class="link-head"><span>${heartbeat.name}</span><span>${heartbeat.ok ? 'ONLINE' : 'DEGRADED'}</span></div>
                <b>${heartbeat.rate} Hz</b>
                <span>心跳丢失 ${heartbeat.missed} 拍</span>
                <div class="heartbeat-bars">${Array.from({ length: 12 }, (_, index) => `<i class="${index < 10 ? (heartbeat.ok ? 'on' : 'warn') : ''}"></i>`).join('')}</div>
              </div>
            `).join('')}
          </div>
          <div class="parser-map" style="margin-top:8px"><div class="parser-map-head"><span>SAFETY ISLAND</span><b>${liveSpan('mcu.hbRda', 0)} Hz</b></div><pre class="parser-code">SOC_LINK  safety_island  OK    latency=1.2ms
SOC_LINK  RDA            WARN  missed=2
SOC_LINK  NRDA           OK    latency=0.8ms
PCIE      Gen3 x4        RETRAIN=2</pre></div>
        `, { sub: 'SAFETY ISLAND / RDA / NRDA' })}
        ${panelHTML('CAN / PCIe / 风扇', 'layers', `
          <table class="data-table">
            <thead><tr><th>项目</th><th>观测值</th><th>状态</th></tr></thead>
            <tbody>
              <tr><td>CAN 总线负载</td><td class="mono">${liveSpan('mcu.canLoad', 0)}% / 错误帧 14</td><td><span class="status-pill warning">关注</span></td></tr>
              <tr><td>PCIe 链路</td><td class="mono">Gen3 ×4 · RETRAIN 2</td><td><span class="status-pill warning">关注</span></td></tr>
              <tr><td>风扇转速</td><td class="mono">${liveSpan('mcu.fanRpm', 0)} RPM</td><td><span class="status-pill healthy">正常</span></td></tr>
              <tr><td>ADC CH4</td><td class="mono">${liveSpan('mcu.adc4', 2)} V / 4.5 V</td><td><span class="status-pill warning">越限</span></td></tr>
            </tbody>
          </table>
        `, { sub: 'BUS + THERMAL' })}
        ${panelHTML('ADC 电压与三核心跳', 'activity', `
          <div class="chart-canvas"><canvas data-chart="mcuMix" aria-label="ADC 电压与三核心跳"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#FB923C"></i>ADC CH4 (V)</span><span class="legend-item"><i style="--legend:#A855F7"></i>RDA HEARTBEAT (Hz)</span></div>
        `, { sub: 'ADC + HEARTBEAT', span2: true })}
      </div>
    `;
  }

  function stabilityDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('稳定性计数', 'activity', `
          <div class="stability-counters">
            <div class="stability-counter critical"><span>PANIC</span><b>${liveSpan('stability.panic', 0)}</b></div>
            <div class="stability-counter critical"><span>异常重启</span><b>${liveSpan('stability.reboot', 0)}</b></div>
            <div class="stability-counter warning"><span>ANR</span><b>${liveSpan('stability.anr', 0)}</b></div>
            <div class="stability-counter critical"><span>CRASH</span><b>${liveSpan('stability.crash', 0)}</b></div>
          </div>
          <div class="parser-map" style="margin-top:8px"><div class="parser-map-head"><span>UPTIME / LAST BOOT</span><b>${liveSpan('stability.uptime', 0)} s</b></div><pre class="parser-code">LAST_BOOT  reason=watchdog
LAST_PANIC kernel=watchdog_hardlockup
LAST_CRASH proc=ivi signal=SIGSEGV</pre></div>
        `, { span2: true, sub: 'PANIC / REBOOT / ANR / CRASH', chip: '<span class="panel-chip">WATCHDOG</span>' })}
        ${panelHTML('24h 稳定性动态绘图', 'gauge', `
          <div class="chart-canvas tall"><canvas data-chart="stability24h" aria-label="24 小时稳定性事件"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#FB7185"></i>INCIDENTS / HOUR</span><span class="legend-item"><i style="--legend:#FBBF24"></i>THRESHOLD</span></div>
        `, { span2: true, sub: 'INCIDENT DENSITY' })}
        ${panelHTML('关键进程状态', 'layers', `
          <table class="data-table">
            <thead><tr><th>进程</th><th>状态</th><th>最近事件</th></tr></thead>
            <tbody>
              <tr><td class="strong">com.nexus.ivi</td><td><span class="status-pill critical">CRASH</span></td><td>10:32:01 SIGSEGV</td></tr>
              <tr><td class="strong">system_server</td><td><span class="status-pill warning">ANR</span></td><td>10:31:55 timeout 5s</td></tr>
              <tr><td class="strong">watchdogd</td><td><span class="status-pill critical">PANIC</span></td><td>10:36:10 hardlockup</td></tr>
              <tr><td class="strong">surfaceflinger</td><td><span class="status-pill healthy">正常</span></td><td>—</td></tr>
            </tbody>
          </table>
        `, { span2: true, sub: 'PROCESS HEALTH' })}
      </div>
    `;
  }

  function powerDetailTemplate() {
    return `
      <div class="detail-panels">
        ${panelHTML('整机功率与温度伴随跳变', 'zap', `
          <div class="chart-canvas tall"><canvas data-chart="powerDual" aria-label="整机功率与温度"></canvas></div>
          <div class="chart-legend"><span class="legend-item"><i style="--legend:#A3E635"></i>POWER (W)</span><span class="legend-item"><i style="--legend:#FB7185"></i>TEMP (°C)</span></div>
        `, { span2: true, sub: 'DUAL AXIS · CORRELATED', chip: '<span class="panel-chip live">LIVE</span>' })}
        ${panelHTML('电源轨拆解', 'layers', `
          <div class="rail-list">
            ${[
              { name: 'SOC', value: 19.4, color: '#4C8DFF' },
              { name: 'DDR', value: 9.2, color: '#A855F7' },
              { name: 'DISPLAY', value: 5.2, color: '#22D3EE' },
              { name: 'RF', value: 3.6, color: '#F59E0B' },
              { name: 'AUDIO', value: 4.1, color: '#EC4899' },
              { name: 'PERIPH', value: 3.3, color: '#34D399' }
            ].map((rail) => `<div class="rail-row"><span>${rail.name}</span><div class="rail-track"><i style="width:${clamp(rail.value / 25 * 100, 5, 100)}%;--rail-color:${rail.color}"></i></div><b>${rail.value} W</b></div>`).join('')}
          </div>
        `, { sub: 'RAIL BREAKDOWN' })}
        ${panelHTML('热与功耗阈值', 'thermometer', `
          <div class="power-cards">
            <div class="power-card"><span>整机功耗</span><b>${liveSpan('power.total', 1)} W</b></div>
            <div class="power-card"><span>SoC 温度</span><b>${liveSpan('power.temp', 1)} °C</b></div>
            <div class="power-card"><span>峰值功率</span><b>${liveSpan('power.peak', 1)} W</b></div>
            <div class="power-card"><span>风扇转速</span><b>${liveSpan('power.fan', 0)} RPM</b></div>
          </div>
          <div class="parser-map" style="margin-top:8px"><div class="parser-map-head"><span>POWER ENVELOPE</span><b>TEMP WALL 80°C</b></div><pre class="parser-code">VCORE SPIKE  68.1W  +25.7W  WARN
PACKAGE TEMP 84.0C  LIMIT 80C
FAN          4100 RPM  HIGH</pre></div>
        `, { sub: 'THERMAL ENVELOPE' })}
      </div>
    `;
  }

  function diagnosisPanel(moduleState) {
    const actions = MODULE_ACTIONS[moduleState.id] || [];
    return panelHTML('AI 诊断结论与处置建议', 'sparkles', `
      <div class="diagnosis-copy">${escapeHtml(moduleState.summary)}</div>
      <div class="action-grid">
        ${actions.map((action, index) => `
          <div class="action-card">
            <span>STEP ${pad2(index + 1)}</span>
            <b>${escapeHtml(action.title)}</b>
            <p>${escapeHtml(action.detail)}</p>
          </div>
        `).join('')}
      </div>
      <div class="diagnosis-foot">
        <span>由日志解析器 + 规则引擎生成 · 建议结合现场复测</span>
        <button class="btn primary" type="button" data-action="export-report">${icon('download')}生成 8D 维修报告</button>
      </div>
    `, { className: 'diagnosis-panel', sub: 'AI RECOMMENDATION', chip: '<span class="panel-chip live">AUTO</span>' });
  }

  function genericDetailTemplate(moduleState) {
    const detail = moduleState.detail || {};
    const stats = (detail.stats || []).map((stat) => {
      let value;
      if (stat.value != null) {
        value = `${stat.value}${stat.unit ? ` <em>${stat.unit}</em>` : ''}`;
      } else {
        value = `${liveSpan(stat.live, stat.digits || 0)}${stat.unit ? ` <em>${stat.unit}</em>` : ''}`;
      }
      return `<div class="soc-stat"><span>${stat.label}</span><b>${value}</b></div>`;
    }).join('');

    const tableRows = (detail.rows || []).map((row) => `
      <tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>
    `).join('');

    const notes = (detail.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join('');
    const legend = (detail.legend || []).map((item) => `<span class="legend-item"><i style="--legend:${item.color}"></i>${item.label}</span>`).join('');

    return `
      <div class="detail-panels">
        ${panelHTML('关键监测指标', 'gauge', `
          <div class="soc-stat-grid">${stats}</div>
          ${detail.rails ? `<div class="rail-list" style="margin-top:9px">${detail.rails.map((rail) => `<div class="rail-row"><span>${rail.label}</span><div class="rail-track"><i style="width:${clamp(rail.value / (rail.max || 100) * 100, 4, 100)}%;--rail-color:${rail.color}"></i></div><b>${rail.display || rail.value}</b></div>`).join('')}</div>` : ''}
        `, { sub: moduleState.en, chip: '<span class="panel-chip live">LIVE</span>' })}
        ${panelHTML('实时监控图', 'activity', `
          <div class="chart-canvas"><canvas data-chart="${detail.chart}" aria-label="${moduleState.name} 实时监控"></canvas></div>
          ${legend ? `<div class="chart-legend">${legend}</div>` : ''}
        `, { sub: 'REAL-TIME TREND' })}
        ${panelHTML(detail.tableTitle || '模块检查项', 'layers', `
          <table class="data-table">
            <thead><tr>${(detail.tableHeaders || []).map((header) => `<th>${header}</th>`).join('')}</tr></thead>
            <tbody>${tableRows}</tbody>
          </table>
        `, { span2: true, sub: 'MODULE SELF-CHECK' })}
        ${notes ? `<section class="panel span-2"><div class="panel-head"><div class="panel-title">${icon('sparkles')}<h2>检查结论</h2><small>OBSERVATION</small></div></div><div class="panel-body"><ul class="generic-notes">${notes}</ul></div></section>` : ''}
      </div>
    `;
  }

  function moduleDetailTemplate(moduleState) {
    let content = '';
    if (moduleState.domain !== 'cdc') {
      content = genericDetailTemplate(moduleState);
    } else {
      switch (moduleState.id) {
        case 'soc': content = socDetailTemplate(); break;
        case 'ddr': content = ddrDetailTemplate(); break;
        case 'storage': content = storageDetailTemplate(); break;
        case 'rf': content = rfDetailTemplate(); break;
        case 'audio': content = audioDetailTemplate(); break;
        case 'peripherals': content = peripheralsDetailTemplate(); break;
      case 'display': content = displayDetailTemplate(); break;
        case 'mcu': content = mcuDetailTemplate(); break;
        case 'stability': content = stabilityDetailTemplate(); break;
        case 'power': content = powerDetailTemplate(); break;
        default: content = '';
      }
    }
    return `${content}${monitorSpecPanel(moduleState)}${diagnosisPanel(moduleState)}`;
  }

  /* ============================================================
     Chart engine
     ============================================================ */

  function chartPalette(report = false) {
    if (report) {
      return { grid: '#e7edf5', axis: '#cbd7e5', text: '#8190a5', background: '#ffffff' };
    }
    if (state.theme === 'light') {
      return { grid: 'rgba(15, 23, 42, 0.07)', axis: 'rgba(15, 23, 42, 0.12)', text: '#7b8aa0', background: 'transparent' };
    }
    return { grid: 'rgba(150, 175, 215, 0.09)', axis: 'rgba(150, 175, 215, 0.16)', text: '#71809a', background: 'transparent' };
  }

  function prepareCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, width, height);
    return { context, width, height };
  }

  function drawSmoothPath(context, points) {
    if (!points.length) return;
    context.moveTo(points[0].x, points[0].y);
    for (let index = 1; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      context.quadraticCurveTo(current.x, current.y, (current.x + next.x) / 2, (current.y + next.y) / 2);
    }
    const last = points[points.length - 1];
    context.lineTo(last.x, last.y);
  }

  function drawSeriesChart(context, width, height, seriesList, options = {}) {
    const palette = options.palette || chartPalette();
    const padding = options.padding || { left: 6, right: 6, top: 8, bottom: 8 };
    const plotWidth = Math.max(1, width - padding.left - padding.right);
    const plotHeight = Math.max(1, height - padding.top - padding.bottom);
    const visibleSeries = seriesList.filter((series) => Array.isArray(series.data) && series.data.length > 1);
    if (!visibleSeries.length) return;

    let minimum = options.min;
    let maximum = options.max;
    if (minimum == null || maximum == null) {
      const values = visibleSeries.flatMap((series) => series.data);
      minimum = minimum == null ? Math.min(...values) : minimum;
      maximum = maximum == null ? Math.max(...values) : maximum;
    }
    if (maximum - minimum < 0.001) maximum = minimum + 1;

    if (options.grid !== false) {
      context.strokeStyle = palette.grid;
      context.lineWidth = 1;
      for (let line = 1; line <= 3; line += 1) {
        const y = padding.top + (plotHeight / 4) * line;
        context.beginPath();
        context.moveTo(padding.left, y);
        context.lineTo(width - padding.right, y);
        context.stroke();
      }
    }

    visibleSeries.forEach((series) => {
      const data = series.data;
      const seriesMin = options.normalizeEach ? Math.min(...data) : minimum;
      const seriesMax = options.normalizeEach ? Math.max(...data) : maximum;
      const range = seriesMax - seriesMin || 1;
      const points = data.map((value, index) => ({
        x: padding.left + index * (plotWidth / (data.length - 1)),
        y: padding.top + plotHeight - ((value - seriesMin) / range) * plotHeight
      }));

      if (series.fill) {
        const gradient = context.createLinearGradient(0, padding.top, 0, height - padding.bottom);
        gradient.addColorStop(0, hexToRgba(series.color, options.report ? 0.18 : 0.15));
        gradient.addColorStop(1, hexToRgba(series.color, 0));
        context.beginPath();
        context.moveTo(points[0].x, height - padding.bottom);
        points.forEach((point) => context.lineTo(point.x, point.y));
        context.lineTo(points[points.length - 1].x, height - padding.bottom);
        context.closePath();
        context.fillStyle = gradient;
        context.fill();
      }

      context.beginPath();
      drawSmoothPath(context, points);
      context.strokeStyle = series.color;
      context.lineWidth = series.width || (options.report ? 2.1 : state.theme === 'light' ? 1.9 : 1.55);
      context.lineJoin = 'round';
      context.lineCap = 'round';
      context.shadowBlur = options.report ? 0 : 7;
      context.shadowColor = hexToRgba(series.color, 0.35);
      context.stroke();
      context.shadowBlur = 0;

      if (series.dot !== false) {
        const last = points[points.length - 1];
        context.beginPath();
        context.arc(last.x, last.y, options.report ? 2.8 : 2, 0, Math.PI * 2);
        context.fillStyle = series.color;
        context.fill();
      }
    });
  }

  function drawDualChart(context, width, height, leftSeries, rightSeries, options = {}) {
    const palette = options.palette || chartPalette();
    const padding = { left: 7, right: 7, top: 8, bottom: 8 };
    const plotWidth = Math.max(1, width - padding.left - padding.right);
    const plotHeight = Math.max(1, height - padding.top - padding.bottom);
    const leftValues = leftSeries.data;
    const rightValues = rightSeries.data;
    let leftMin = Math.min(...leftValues);
    let leftMax = Math.max(...leftValues);
    let rightMin = Math.min(...rightValues);
    let rightMax = Math.max(...rightValues);
    if (leftMax - leftMin < 0.001) leftMax = leftMin + 1;
    if (rightMax - rightMin < 0.001) rightMax = rightMin + 1;
    leftMin -= (leftMax - leftMin) * 0.08;
    leftMax += (leftMax - leftMin) * 0.08;
    rightMin -= (rightMax - rightMin) * 0.08;
    rightMax += (rightMax - rightMin) * 0.08;

    context.strokeStyle = palette.grid;
    context.lineWidth = 1;
    for (let line = 1; line <= 3; line += 1) {
      const y = padding.top + (plotHeight / 4) * line;
      context.beginPath();
      context.moveTo(padding.left, y);
      context.lineTo(width - padding.right, y);
      context.stroke();
    }

    const drawScaled = (data, color, min, max, fill) => {
      const range = max - min || 1;
      const points = data.map((value, index) => ({
        x: padding.left + index * (plotWidth / (data.length - 1)),
        y: padding.top + plotHeight - ((value - min) / range) * plotHeight
      }));
      if (fill) {
        const gradient = context.createLinearGradient(0, padding.top, 0, height - padding.bottom);
        gradient.addColorStop(0, hexToRgba(color, 0.14));
        gradient.addColorStop(1, hexToRgba(color, 0));
        context.beginPath();
        context.moveTo(points[0].x, height - padding.bottom);
        points.forEach((point) => context.lineTo(point.x, point.y));
        context.lineTo(points[points.length - 1].x, height - padding.bottom);
        context.closePath();
        context.fillStyle = gradient;
        context.fill();
      }
      context.beginPath();
      drawSmoothPath(context, points);
      context.strokeStyle = color;
      context.lineWidth = options.report ? 2.1 : state.theme === 'light' ? 1.9 : 1.55;
      context.lineJoin = 'round';
      context.lineCap = 'round';
      context.shadowBlur = options.report ? 0 : 6;
      context.shadowColor = hexToRgba(color, 0.35);
      context.stroke();
      context.shadowBlur = 0;
      const last = points[points.length - 1];
      context.beginPath();
      context.arc(last.x, last.y, 2, 0, Math.PI * 2);
      context.fillStyle = color;
      context.fill();
    };

    drawScaled(leftValues, leftSeries.color, leftMin, leftMax, true);
    drawScaled(rightValues, rightSeries.color, rightMin, rightMax, false);
  }

  function drawBarsChart(context, width, height, data, color, options = {}) {
    const palette = options.palette || chartPalette();
    const padding = { left: 7, right: 7, top: 9, bottom: 9 };
    const plotWidth = Math.max(1, width - padding.left - padding.right);
    const plotHeight = Math.max(1, height - padding.top - padding.bottom);
    const max = Math.max(...data, 1);
    context.strokeStyle = palette.grid;
    context.lineWidth = 1;
    for (let line = 1; line <= 3; line += 1) {
      const y = padding.top + (plotHeight / 4) * line;
      context.beginPath();
      context.moveTo(padding.left, y);
      context.lineTo(width - padding.right, y);
      context.stroke();
    }
    const gap = 3;
    const barWidth = Math.max(2, (plotWidth - gap * (data.length - 1)) / data.length);
    data.forEach((value, index) => {
      const barHeight = clamp((value / max) * plotHeight, 2, plotHeight);
      const x = padding.left + index * (barWidth + gap);
      const y = padding.top + plotHeight - barHeight;
      context.fillStyle = index === data.length - 1 ? color : hexToRgba(color, 0.55);
      if (typeof context.roundRect === 'function') {
        context.beginPath();
        context.roundRect(x, y, barWidth, barHeight, 1.5);
        context.fill();
      } else {
        context.fillRect(x, y, barWidth, barHeight);
      }
    });
    const thresholdY = padding.top + plotHeight - (2 / max) * plotHeight;
    context.setLineDash([3, 3]);
    context.strokeStyle = hexToRgba('#FBBF24', 0.65);
    context.beginPath();
    context.moveTo(padding.left, thresholdY);
    context.lineTo(width - padding.right, thresholdY);
    context.stroke();
    context.setLineDash([]);
  }

  function miniSeries(moduleId) {
    const history = state.history;
    switch (moduleId) {
      case 'soc':
        return [
          { data: history.socCpu, color: '#4C8DFF', fill: true },
          { data: history.socGpu, color: '#A855F7' },
          { data: history.socNpu, color: '#22D3EE' }
        ];
      case 'ddr':
        return [
          { data: history.ddr0, color: '#4C8DFF' },
          { data: history.ddr1, color: '#22D3EE' },
          { data: history.ddr2, color: '#FB7185', fill: true },
          { data: history.ddr3, color: '#A855F7' }
        ];
      case 'storage':
        return [
          { data: history.stoRead, color: '#22D3EE', fill: true },
          { data: history.stoWrite, color: '#A3E635' }
        ];
      case 'rf':
        return [
          { data: history.rf5g, color: '#F59E0B', fill: true },
          { data: history.rfWifi, color: '#4C8DFF' },
          { data: history.rfBt, color: '#EC4899' },
          { data: history.rfNfc, color: '#22D3EE' }
        ];
      case 'audio':
        return [
          { data: history.mic1, color: '#EC4899', fill: true },
          { data: history.mic2, color: '#A855F7' },
          { data: history.mic3, color: '#F59E0B' },
          { data: history.mic4, color: '#22D3EE' }
        ];
      case 'peripherals':
        return [
          { data: history.camFront, color: '#34D399', fill: true },
          { data: history.camRear, color: '#22D3EE' },
          { data: history.camDms, color: '#A855F7' },
          { data: history.camOms, color: '#F59E0B' }
        ];
      case 'mcu':
        return [
          { data: history.mcuAdc, color: '#FB923C', fill: true, normalize: true },
          { data: history.hbRda, color: '#A855F7', normalize: true }
        ];
      case 'power':
        return [
          { data: history.pwr, color: '#A3E635', fill: true, normalize: true },
          { data: history.temp, color: '#FB7185', normalize: true }
        ];
      case 'mdc-compute':
        return [
          { data: history.mdcCpu, color: '#22D3EE', fill: true },
          { data: history.mdcNpu0, color: '#F472B6' },
          { data: history.mdcGpu, color: '#60A5FA' }
        ];
      case 'mdc-ddr':
        return [
          { data: history.mdcDdr, color: '#38BDF8', fill: true },
          { data: history.mdcBw, color: '#818CF8', normalize: true }
        ];
      case 'mdc-storage':
        return [
          { data: history.mdcSto, color: '#818CF8', fill: true },
          { data: history.mdcPwr, color: '#FBBF24', normalize: true }
        ];
      case 'mdc-perception':
        return [
          { data: history.mdcCam, color: '#2DD4BF', fill: true },
          { data: history.mdcLidar, color: '#F472B6', normalize: true }
        ];
      case 'mdc-network':
        return [
          { data: history.mdcEth, color: '#60A5FA', fill: true },
          { data: history.mdcLoss, color: '#FBBF24', normalize: true }
        ];
      case 'mdc-safety':
        return [
          { data: history.mdcHeart, color: '#F472B6', fill: true },
          { data: history.mdcTemp, color: '#22D3EE', normalize: true }
        ];
      case 'mdc-power':
        return [
          { data: history.mdcPwr, color: '#FBBF24', fill: true, normalize: true },
          { data: history.mdcTemp, color: '#FB7185', normalize: true }
        ];
      case 'vdc-soc':
        return [
          { data: history.vdcCpu, color: '#A3E635', fill: true },
          { data: history.mdcHeart, color: '#22D3EE', normalize: true }
        ];
      case 'vdc-io':
        return [
          { data: history.vdcIo, color: '#34D399', fill: true },
          { data: history.vdcCan, color: '#FBBF24', normalize: true }
        ];
      case 'vdc-chassis':
        return [
          { data: history.vdcBrake, color: '#FBBF24', fill: true },
          { data: history.vdcSteer, color: '#34D399', normalize: true }
        ];
      case 'vdc-network':
        return [
          { data: history.vdcCan, color: '#22D3EE', fill: true },
          { data: history.vdcLin, color: '#FB7185', normalize: true }
        ];
      case 'vdc-power':
        return [
          { data: history.vdcVolt, color: '#FB923C', fill: true, normalize: true },
          { data: history.vdcCurr, color: '#A3E635', normalize: true }
        ];
      case 'vdc-diagnostics':
        return [
          { data: history.vdcDtc, color: '#C084FC', fill: true, normalize: true },
          { data: history.vdcOta, color: '#34D399', normalize: true }
        ];
      case 'vdc-stability':
        return [
          { data: history.vdcResets, color: '#FB7185', fill: true, normalize: true },
          { data: history.vdcCpu, color: '#A3E635', normalize: true }
        ];
      default:
        return [];
    }
  }

  function drawMiniChart(context, width, height, moduleId, report = false) {
    const palette = chartPalette(report);
    if (report) {
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, width, height);
    }
    if (moduleId === 'stability') {
      drawBarsChart(context, width, height, state.live.stability.hourly, '#FB7185', { palette, report });
      return;
    }
    if (moduleId === 'power') {
      drawDualChart(context, width, height,
        { data: state.history.pwr, color: '#A3E635' },
        { data: state.history.temp, color: '#FB7185' },
        { palette, report });
      return;
    }
    if (moduleId === 'mcu') {
      drawSeriesChart(context, width, height, [
        { data: state.history.mcuAdc, color: '#FB923C', fill: true },
        { data: state.history.hbRda, color: '#A855F7' }
      ], { palette, report, normalizeEach: true, grid: false, padding: { left: 4, right: 4, top: 6, bottom: 6 } });
      return;
    }
    const series = miniSeries(moduleId);
    drawSeriesChart(context, width, height, series, {
      palette,
      report,
      grid: false,
      normalizeEach: series.some((item) => item.normalize),
      padding: { left: 4, right: 4, top: 6, bottom: 6 }
    });
  }

  function detailChartSeries(type) {
    const history = state.history;
    switch (type) {
      case 'ddrChannels':
        return [
          { data: history.ddr0, color: '#A855F7', fill: true },
          { data: history.ddr1, color: '#4C8DFF' },
          { data: history.ddr2, color: '#FB7185' },
          { data: history.ddr3, color: '#22D3EE' }
        ];
      case 'storageIO':
        return [
          { data: history.stoRead, color: '#22D3EE', fill: true },
          { data: history.stoWrite, color: '#A3E635' }
        ];
      case 'rfScope':
        return [
          { data: history.rf5g, color: '#F59E0B', fill: true },
          { data: history.rfWifi, color: '#4C8DFF' },
          { data: history.rfBt, color: '#EC4899' },
          { data: history.rfNfc, color: '#22D3EE' }
        ];
      case 'audioLevels':
        return [
          { data: history.mic1, color: '#EC4899', fill: true },
          { data: history.mic2, color: '#A855F7' },
          { data: history.mic3, color: '#F59E0B' },
          { data: history.mic4, color: '#22D3EE' }
        ];
      case 'periphFps':
        return [
          { data: history.camFront, color: '#34D399', fill: true },
          { data: history.camRear, color: '#22D3EE' },
          { data: history.camDms, color: '#A855F7' },
          { data: history.camOms, color: '#F59E0B' }
        ];
      case 'mdcCompute':
        return [
          { data: history.mdcCpu, color: '#22D3EE', fill: true },
          { data: history.mdcNpu0, color: '#F472B6' },
          { data: history.mdcNpu1, color: '#A78BFA' },
          { data: history.mdcGpu, color: '#60A5FA' }
        ];
      case 'mdcDdr':
        return [
          { data: history.mdcDdr, color: '#38BDF8', fill: true },
          { data: history.mdcBw, color: '#818CF8' },
          { data: history.mdcCpu, color: '#22D3EE', normalize: true }
        ];
      case 'mdcStorage':
        return [
          { data: history.mdcSto, color: '#818CF8', fill: true, normalize: true },
          { data: history.mdcPwr, color: '#FBBF24', normalize: true }
        ];
      case 'mdcPerception':
        return [
          { data: history.mdcCam, color: '#2DD4BF', fill: true, normalize: true },
          { data: history.mdcLidar, color: '#F472B6', normalize: true }
        ];
      case 'mdcNetwork':
        return [
          { data: history.mdcEth, color: '#60A5FA', fill: true, normalize: true },
          { data: history.mdcLoss, color: '#FBBF24', normalize: true }
        ];
      case 'mdcSafety':
        return [
          { data: history.mdcHeart, color: '#F472B6', fill: true, normalize: true },
          { data: history.mdcTemp, color: '#22D3EE', normalize: true }
        ];
      case 'vdcSoc':
        return [
          { data: history.vdcCpu, color: '#A3E635', fill: true },
          { data: history.vdcCan, color: '#22D3EE', normalize: true }
        ];
      case 'vdcIo':
        return [
          { data: history.vdcIo, color: '#34D399', fill: true, normalize: true },
          { data: history.vdcCan, color: '#FBBF24', normalize: true }
        ];
      case 'vdcChassis':
        return [
          { data: history.vdcBrake, color: '#FBBF24', fill: true, normalize: true },
          { data: history.vdcSteer, color: '#34D399', normalize: true }
        ];
      case 'vdcNetwork':
        return [
          { data: history.vdcCan, color: '#22D3EE', fill: true, normalize: true },
          { data: history.vdcLin, color: '#FB7185', normalize: true }
        ];
      case 'vdcDiag':
        return [
          { data: history.vdcDtc, color: '#C084FC', fill: true, normalize: true },
          { data: history.vdcOta, color: '#34D399', normalize: true }
        ];
      case 'vdcStability':
        return [
          { data: history.vdcResets, color: '#FB7185', fill: true, normalize: true },
          { data: history.vdcCpu, color: '#A3E635', normalize: true }
        ];
      default:
        return [];
    }
  }

  function drawDetailChart(context, width, height, type) {
    const palette = chartPalette();
    switch (type) {
      case 'socPower':
        drawDualChart(context, width, height,
          { data: state.history.socPower, color: '#4C8DFF' },
          { data: state.history.socTemp, color: '#FB7185' },
          { palette });
        break;
      case 'powerDual':
        drawDualChart(context, width, height,
          { data: state.history.pwr, color: '#A3E635' },
          { data: state.history.temp, color: '#FB7185' },
          { palette });
        break;
      case 'mcuMix':
        drawSeriesChart(context, width, height, [
          { data: state.history.mcuAdc, color: '#FB923C', fill: true },
          { data: state.history.hbRda, color: '#A855F7' }
        ], { palette, normalizeEach: true });
        break;
      case 'stability24h':
        drawBarsChart(context, width, height, state.live.stability.hourly, '#FB7185', { palette });
        break;
      case 'mdcPower':
        drawDualChart(context, width, height,
          { data: state.history.mdcPwr, color: '#FBBF24' },
          { data: state.history.mdcTemp, color: '#FB7185' },
          { palette });
        break;
      case 'vdcPower':
        drawDualChart(context, width, height,
          { data: state.history.vdcVolt, color: '#FB923C' },
          { data: state.history.vdcCurr, color: '#A3E635' },
          { palette });
        break;
      default: {
        const series = detailChartSeries(type);
        drawSeriesChart(context, width, height, series, {
          palette,
          normalizeEach: series.some((item) => item.normalize)
        });
        break;
      }
    }
  }

  function clearCharts() {
    CHART_ENTRIES.clear();
  }

  function registerChart(canvas, draw) {
    CHART_ENTRIES.set(canvas, draw);
  }

  function mountCharts() {
    clearCharts();
    $$('canvas[data-mini]').forEach((canvas) => {
      registerChart(canvas, (context, width, height) => drawMiniChart(context, width, height, canvas.dataset.mini));
    });
    $$('canvas[data-chart]').forEach((canvas) => {
      registerChart(canvas, (context, width, height) => drawDetailChart(context, width, height, canvas.dataset.chart));
    });
  }

  function chartLoop(timestamp) {
    window.requestAnimationFrame(chartLoop);
    if (document.hidden) return;
    if (timestamp - lastChartFrame < 1000 / 30) return;
    lastChartFrame = timestamp;
    let drawn = 0;
    CHART_ENTRIES.forEach((draw, canvas) => {
      if (!canvas.isConnected) {
        CHART_ENTRIES.delete(canvas);
        return;
      }
      const rect = canvas.getBoundingClientRect();
      if (rect.bottom < -60 || rect.top > window.innerHeight + 60 || rect.right < 0 || rect.left > window.innerWidth) return;
      const prepared = prepareCanvas(canvas);
      if (!prepared) return;
      draw(prepared.context, prepared.width, prepared.height);
      drawn += 1;
    });
    if (drawn > 0) fpsFrames += 1;
    const now = performance.now();
    if (now - fpsStartedAt >= 1000 && fpsFrames > 0) {
      state.fps = Math.round((fpsFrames * 1000) / (now - fpsStartedAt));
      fpsFrames = 0;
      fpsStartedAt = now;
      const displayFps = state.fps >= 12 ? 30 : state.fps;
      setText('#fpsValue', displayFps);
      setText('#kpiFpsValue', displayFps);
      const fpsChip = $('.fps-chip');
      if (fpsChip) fpsChip.title = `目标 30 FPS · 实测 ${state.fps} FPS`;
    }
  }

  /* ============================================================
     Telemetry and live bindings
     ============================================================ */

  function pushSeries(key, value) {
    const history = state.history[key];
    if (!history) return;
    history.push(round(value, 3));
    if (history.length > 60) history.shift();
  }

  function updateTelemetry() {
    const timestamp = performance.now() / 1000;
    const live = state.live;

    live.soc.cores.forEach((core, index) => {
      const base = [58, 44, 61, 16, 55, 63, 49, 72, 57, 46, 60, 52][index];
      core.load = clamp(base + Math.sin(timestamp * (0.4 + index * 0.025) + index) * 7 + rand(-1.6, 1.6), 6, 97);
      core.temp = clamp(52 + core.load * 0.18 + Math.sin(timestamp * 0.3 + index) * 1.2, 46, 86);
      core.freq = index === 7 && core.load > 68 ? 2.4 : 1.8;
      core.voltage = index === 3 ? 0.71 : 0.82;
      core.warn = index === 3;
    });
    live.soc.cpuAvg = live.soc.cores.reduce((total, core) => total + core.load, 0) / 12;
    live.soc.gpu = clamp(58 + Math.sin(timestamp * 0.55) * 4 + rand(-1.3, 1.3), 32, 82);
    live.soc.npu = clamp(47 + Math.sin(timestamp * 0.42 + 2) * 5 + rand(-1.2, 1.2), 26, 76);
    live.soc.mpu = clamp(38 + Math.sin(timestamp * 0.3 + 3) * 3, 24, 56);
    live.soc.temp = clamp(71 + live.soc.cpuAvg * 0.06 + Math.sin(timestamp * 0.18) * 0.8, 65, 82);
    live.soc.power = clamp(18.4 + live.soc.cpuAvg * 0.028 + Math.sin(timestamp * 0.5) * 0.7, 16, 24);
    live.soc.eccCe = 12 + (Math.sin(timestamp * 0.08) > 0.92 ? 1 : 0);
    live.soc.eccUe = 0;

    live.ddr.usage = clamp(74 + Math.sin(timestamp * 0.32) * 2.2 + rand(-0.4, 0.4), 64, 84);
    live.ddr.jump = clamp(1.6 + Math.abs(Math.sin(timestamp * 0.7)) * 1.8, 0.8, 5.4);
    live.ddr.bandwidth = clamp(31 + Math.sin(timestamp * 0.28) * 2.5, 24, 37);
    live.ddr.channels.forEach((channel, index) => {
      const bases = [78, 71, 91, 67];
      channel.usage = clamp(bases[index] + Math.sin(timestamp * 0.34 + index) * 3 + rand(-0.8, 0.8), 52, 96);
      channel.bandwidth = clamp(channel.usage / 100 * 10.4 + rand(-0.3, 0.3), 4, 10.8);
    });

    live.storage.usage = clamp(78.4 + Math.sin(timestamp * 0.04) * 0.08, 74, 82);
    live.storage.read = clamp(430 + Math.sin(timestamp * 0.44) * 34 + rand(-10, 10), 260, 520);
    live.storage.write = clamp(126 + Math.sin(timestamp * 0.31 + 2) * 18 + rand(-6, 6), 70, 180);
    live.storage.latency = clamp(18 + Math.abs(Math.sin(timestamp * 0.22)) * 4, 12, 32);
    live.storage.bad = 3;
    live.storage.life = 91;

    live.rf.rsrp2g = -89 + Math.sin(timestamp * 0.3) * 2;
    live.rf.rsrp3g = -96 + Math.sin(timestamp * 0.28) * 2;
    live.rf.rsrp4g = -84 + Math.sin(timestamp * 0.36) * 3;
    live.rf.rsrp5g = -98 + Math.sin(timestamp * 0.42) * 4;
    live.rf.wifiRssi = -54 + Math.sin(timestamp * 0.5) * 2;
    live.rf.btRssi = -71 + Math.sin(timestamp * 0.63) * 2;
    live.rf.nearlinkRssi = -62 + Math.sin(timestamp * 0.58 + 2) * 2;
    live.rf.nfcRssi = -46 + Math.sin(timestamp * 0.7) * 3;
    live.rf.quality5g = clamp(64 + Math.sin(timestamp * 0.42) * 6, 42, 80);
    live.rf.qualityWifi = clamp(83 + Math.sin(timestamp * 0.35 + 2) * 4, 68, 94);
    live.rf.qualityBt = clamp(68 + Math.sin(timestamp * 0.52 + 1) * 5, 50, 82);
    live.rf.qualityNfc = clamp(46 + Math.sin(timestamp * 0.6 + 3) * 6, 30, 66);

    live.audio.jitter = clamp(2.2 + Math.abs(Math.sin(timestamp * 0.4)) * 1.4, 1.2, 4.2);
    live.audio.micLevels = [
      clamp(-32 + Math.sin(timestamp * 0.5) * 4, -46, -22),
      clamp(-38 + Math.sin(timestamp * 0.44 + 1) * 4, -52, -28),
      clamp(-58 + Math.sin(timestamp * 0.37 + 2) * 3, -68, -48),
      clamp(-35 + Math.sin(timestamp * 0.47 + 3) * 4, -48, -24)
    ];
    live.audio.fmSignal = clamp(62 + Math.sin(timestamp * 0.3) * 3, 52, 72);
    live.audio.amSnr = 12;

    live.peripherals.camFps = clamp(24 + Math.sin(timestamp * 0.31) * 2.4, 18, 28);
    live.peripherals.drop = 18 + Math.floor(Math.abs(Math.sin(timestamp * 0.05)) * 8);
    live.peripherals.displaysOnline = 5;

    live.mcu.adc4 = clamp(4.62 + Math.sin(timestamp * 0.2) * 0.05, 4.45, 4.8);
    live.mcu.canLoad = clamp(78 + Math.sin(timestamp * 0.3) * 4, 58, 88);
    live.mcu.fanRpm = clamp(3200 + Math.sin(timestamp * 0.18) * 140, 2800, 3600);
    live.mcu.hbRda = clamp(58 + Math.sin(timestamp * 0.8) * 2, 52, 62);
    live.mcu.heartbeats[1].rate = round(live.mcu.hbRda, 0);

    live.stability.uptime += 0.5;
    live.stability.panic = 1;
    live.stability.reboot = 2;
    live.stability.anr = 3;
    live.stability.crash = 1;
    const stabilityLast = live.stability.hourly.length - 1;
    live.stability.hourly[stabilityLast] = clamp(1.6 + Math.sin(timestamp * 0.18) * 1.6 + rand(-0.35, 0.35), 0, 4.4);

    live.power.total = clamp(42.4 + Math.sin(timestamp * 0.32) * 3.2, 34, 52);
    live.power.temp = clamp(72.2 + Math.sin(timestamp * 0.26 + 1) * 2.4, 64, 86);
    live.power.peak = 68.1;
    live.power.fan = 4100;

    live.mdc.cpuAvg = clamp(58 + Math.sin(timestamp * 0.34) * 6 + rand(-1, 1), 42, 76);
    live.mdc.npu0 = clamp(72 + Math.sin(timestamp * 0.43 + 1) * 7, 55, 88);
    live.mdc.npu1 = clamp(68 + Math.sin(timestamp * 0.38 + 2) * 6, 50, 84);
    live.mdc.gpu = clamp(44 + Math.sin(timestamp * 0.29 + 3) * 5, 30, 62);
    live.mdc.temp = clamp(77 + live.mdc.npu0 * 0.06 + Math.sin(timestamp * 0.2) * 1.2, 68, 88);
    live.mdc.power = clamp(62 + live.mdc.npu0 * 0.16 + Math.sin(timestamp * 0.35) * 2.2, 50, 88);
    live.mdc.ddrUsage = clamp(66 + Math.sin(timestamp * 0.24) * 2.2, 58, 76);
    live.mdc.ddrBandwidth = clamp(48 + Math.sin(timestamp * 0.3 + 1) * 3, 40, 56);
    live.mdc.ddrTemp = clamp(70 + Math.sin(timestamp * 0.2 + 2) * 1.5, 64, 78);
    live.mdc.ddrCh0 = clamp(68 + Math.sin(timestamp * 0.28) * 3, 56, 82);
    live.mdc.ddrCh1 = clamp(61 + Math.sin(timestamp * 0.31 + 1) * 3, 50, 76);
    live.mdc.ddrCh2 = clamp(78 + Math.sin(timestamp * 0.27 + 2) * 4, 64, 92);
    live.mdc.ddrCh3 = clamp(55 + Math.sin(timestamp * 0.33 + 3) * 3, 44, 68);
    live.mdc.ddrBw0 = live.mdc.ddrCh0 / 100 * 13.6;
    live.mdc.ddrBw1 = live.mdc.ddrCh1 / 100 * 13.6;
    live.mdc.ddrBw2 = live.mdc.ddrCh2 / 100 * 13.6;
    live.mdc.ddrBw3 = live.mdc.ddrCh3 / 100 * 13.6;
    live.mdc.modelLatency = clamp(128 + Math.sin(timestamp * 0.22) * 14, 96, 168);
    live.mdc.storageRead = clamp(1240 + Math.sin(timestamp * 0.3) * 90, 900, 1480);
    live.mdc.sensorLatency = clamp(42 + Math.sin(timestamp * 0.35) * 6, 28, 60);
    live.mdc.cameraFps = clamp(29.2 + Math.sin(timestamp * 0.4) * 1.2, 26, 30);
    live.mdc.lidarDrop = clamp(3.4 + Math.abs(Math.sin(timestamp * 0.24)) * 2.4, 0.4, 6.2);
    live.mdc.ethLatency = clamp(172 + Math.sin(timestamp * 0.4) * 22, 120, 230);
    live.mdc.packetLoss = clamp(0.4 + Math.abs(Math.sin(timestamp * 0.28)) * 0.6, 0.02, 1.2);
    live.mdc.ptpOffset = clamp(1.2 + Math.abs(Math.sin(timestamp * 0.3)) * 1.1, 0.3, 2.6);
    live.mdc.heartbeat = clamp(60 + Math.sin(timestamp * 0.8) * 1.2, 57, 62);
    live.mdc.fan = clamp(5000 + Math.sin(timestamp * 0.22) * 260, 4400, 5600);

    live.vdc.cpuLoad = clamp(42 + Math.sin(timestamp * 0.3) * 5, 28, 62);
    live.vdc.safetyIsland = clamp(60 + Math.sin(timestamp * 0.7) * 1.2, 56, 62);
    live.vdc.temp = clamp(62 + Math.sin(timestamp * 0.18) * 2, 54, 72);
    live.vdc.power = clamp(12.8 + Math.sin(timestamp * 0.26) * 1.1, 10.2, 16.4);
    live.vdc.heartbeat = clamp(60 + Math.sin(timestamp * 0.66) * 1.2, 56, 62);
    live.vdc.canLoad = clamp(74 + Math.sin(timestamp * 0.24) * 6, 58, 88);
    live.vdc.ioLatency = clamp(8.2 + Math.abs(Math.sin(timestamp * 0.32)) * 3, 4, 18);
    live.vdc.brakePressure = clamp(2 + Math.abs(Math.sin(timestamp * 0.15)) * 8, 0, 14);
    live.vdc.steeringAngle = clamp(Math.sin(timestamp * 0.18) * 2.4, -4, 4);
    live.vdc.torque = clamp(210 + Math.sin(timestamp * 0.2) * 18, 170, 250);
    live.vdc.suspension = clamp(1.2 + Math.abs(Math.sin(timestamp * 0.12)) * 1.6, 0, 4);
    live.vdc.voltage12 = clamp(11.94 + Math.sin(timestamp * 0.4) * 0.1 - (Math.sin(timestamp * 0.08) > 0.985 ? 0.18 : 0), 11.62, 12.18);
    live.vdc.quiescent = clamp(18 + Math.sin(timestamp * 0.1) * 1.2, 15, 23);
    live.vdc.dcDc = clamp(13.82 + Math.sin(timestamp * 0.2) * 0.04, 13.7, 13.95);
    live.vdc.ota = clamp(72 + Math.sin(timestamp * 0.06) * 1.2, 70, 76);
    live.vdc.diagReq = clamp(24 + Math.sin(timestamp * 0.5) * 5, 14, 36);
    live.vdc.dtc = 4;
    live.vdc.resets = 1;
    live.vdc.faults = 2;
    live.vdc.actuatorFaults = 1;
    live.vdc.doorFaults = 0;
    live.vdc.lightFaults = 0;
    live.vdc.linTimeouts = 3;

    pushSeries('socCpu', live.soc.cpuAvg);
    pushSeries('socGpu', live.soc.gpu);
    pushSeries('socNpu', live.soc.npu);
    live.ddr.channels.forEach((channel, index) => pushSeries(`ddr${index}`, channel.usage));
    pushSeries('stoRead', live.storage.read);
    pushSeries('stoWrite', live.storage.write);
    pushSeries('rf5g', live.rf.quality5g);
    pushSeries('rfWifi', live.rf.qualityWifi);
    pushSeries('rfBt', live.rf.qualityBt);
    pushSeries('rfNfc', live.rf.qualityNfc);
    live.audio.micLevels.forEach((level, index) => pushSeries(`mic${index + 1}`, clamp(100 + level, 0, 100)));
    pushSeries('camFront', live.peripherals.camFps);
    pushSeries('camRear', 30);
    pushSeries('camDms', 30);
    pushSeries('camOms', 29.5);
    pushSeries('mcuAdc', live.mcu.adc4);
    pushSeries('hbRda', live.mcu.hbRda);
    pushSeries('socPower', live.soc.power);
    pushSeries('socTemp', live.soc.temp);
    pushSeries('pwr', live.power.total);
    pushSeries('temp', live.power.temp);
    pushSeries('mdcCpu', live.mdc.cpuAvg);
    pushSeries('mdcNpu0', live.mdc.npu0);
    pushSeries('mdcNpu1', live.mdc.npu1);
    pushSeries('mdcGpu', live.mdc.gpu);
    pushSeries('mdcDdr', live.mdc.ddrUsage);
    pushSeries('mdcBw', live.mdc.ddrBandwidth);
    pushSeries('mdcSto', live.mdc.storageRead);
    pushSeries('mdcCam', live.mdc.cameraFps);
    pushSeries('mdcLidar', live.mdc.lidarDrop);
    pushSeries('mdcEth', live.mdc.ethLatency);
    pushSeries('mdcLoss', live.mdc.packetLoss);
    pushSeries('mdcHeart', live.mdc.heartbeat);
    pushSeries('mdcPwr', live.mdc.power);
    pushSeries('mdcTemp', live.mdc.temp);
    pushSeries('vdcCpu', live.vdc.cpuLoad);
    pushSeries('vdcIo', live.vdc.ioLatency);
    pushSeries('vdcBrake', live.vdc.brakePressure);
    pushSeries('vdcSteer', live.vdc.steeringAngle);
    pushSeries('vdcCan', live.vdc.canLoad);
    pushSeries('vdcLin', live.vdc.linTimeouts);
    pushSeries('vdcVolt', live.vdc.voltage12);
    pushSeries('vdcCurr', live.vdc.quiescent);
    pushSeries('vdcDtc', live.vdc.dtc);
    pushSeries('vdcOta', live.vdc.ota);
    pushSeries('vdcResets', live.vdc.resets);

    updateLiveLabels();
    updateCoreDom();
  }

  function updateLiveLabels() {
    $$('[data-live]').forEach((element) => {
      const value = getPath(state.live, element.dataset.live);
      if (value == null || Number.isNaN(Number(value))) return;
      const digits = Number(element.dataset.digits || 0);
      element.textContent = Number(value).toFixed(digits);
    });
    $$('[data-live-width]').forEach((element) => {
      const value = getPath(state.live, element.dataset.liveWidth);
      if (value == null) return;
      const max = Number(element.dataset.max || 100);
      element.style.width = `${clamp((Number(value) / max) * 100, 0, 100)}%`;
    });
  }

  function updateCoreDom() {
    state.live.soc.cores.forEach((core, index) => {
      const load = document.querySelector(`[data-core-load="${index}"]`);
      const bar = document.querySelector(`[data-core-bar="${index}"]`);
      const temp = document.querySelector(`[data-core-temp="${index}"]`);
      const freq = document.querySelector(`[data-core-freq="${index}"]`);
      const card = document.querySelector(`[data-core="${index}"]`);
      if (load) load.textContent = `${fmt(core.load, 0)}%`;
      if (bar) bar.style.width = `${core.load}%`;
      if (temp) temp.textContent = `${fmt(core.temp, 0)}°C`;
      if (freq) freq.textContent = `${fmt(core.freq, 2)}GHz`;
      if (card) card.classList.toggle('warn', core.warn);
    });
  }

  /* ============================================================
     Modal / log import
     ============================================================ */

  function openModal(html, mode) {
    const layer = $('#modalRoot');
    if (!layer) return;
    state.modalMode = mode;
    layer.innerHTML = html;
    layer.classList.add('open');
    layer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => $('.modal-close')?.focus(), 50);
  }

  function closeModal() {
    const layer = $('#modalRoot');
    if (!layer) return;
    layer.classList.remove('open');
    layer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    state.modalMode = null;
    window.setTimeout(() => {
      if (!layer.classList.contains('open')) layer.innerHTML = '';
    }, 230);
  }

  function openLogModal() {
    state.pendingLogName = null;
    openModal(`
      <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="logModalTitle">
        <div class="modal-head">
          <div>
            <span class="eyebrow">LOG INGESTION · PARSER v2.4</span>
            <h2 id="logModalTitle">导入并解析诊断日志</h2>
            <p>支持带时间戳、模块标签、等级与 code 字段的文本日志；解析后自动刷新 CDC / MDC / VDC 三域模块时间轴。</p>
          </div>
          <button class="icon-btn modal-close" type="button" data-action="close-modal" aria-label="关闭">${icon('close')}</button>
        </div>
        <div class="modal-body">
          <div class="log-tools">
            <label class="file-label">${icon('file')}选择 .log / .txt 文件<input id="logFile" type="file" accept=".log,.txt,text/plain"></label>
            <span class="log-note" id="logFileName">当前：${escapeHtml(state.sourceName)}</span>
          </div>
          <textarea class="log-textarea" id="logInput" spellcheck="false" aria-label="诊断日志内容">${escapeHtml(state.sourceLogs)}</textarea>
          <div class="log-tools" style="margin-top:7px">
            <button class="btn subtle" type="button" data-action="load-sample">${icon('refresh')}载入示例日志</button>
            <span class="log-note">必填字段：时间 / [MODULE] / [LEVEL] / code=…</span>
          </div>
          <div class="parse-result" id="logParseResult" hidden></div>
        </div>
        <div class="modal-foot">
          <span class="modal-foot-note">原始日志仅在浏览器本地解析，不会上传。</span>
          <div class="modal-actions">
            <button class="btn subtle" type="button" data-action="close-modal">取消</button>
            <button class="btn primary" type="button" data-action="parse-log">${icon('scan')}解析并刷新</button>
          </div>
        </div>
      </div>
    `, 'log');

    const fileInput = $('#logFile');
    fileInput?.addEventListener('change', async () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const textarea = $('#logInput');
        if (textarea) textarea.value = text;
        state.pendingLogName = file.name;
        setText('#logFileName', `当前：${file.name} · ${fmtInt(text.length)} chars`);
      } catch (error) {
        toast('文件读取失败', 'error');
      }
    });
  }

  function validateAndLoadLog() {
    const textarea = $('#logInput');
    if (!textarea) return;
    const text = textarea.value;
    if (!text.trim()) {
      toast('请先粘贴日志或载入示例日志', 'warn');
      return;
    }
    const parsed = parseDiagnosticLogs(text);
    const result = $('#logParseResult');
    if (result) {
      result.hidden = false;
      if (!parsed.events.length) {
        result.className = 'parse-result error';
        result.textContent = `未解析到有效事件：共 ${parsed.totalLines} 行，跳过 ${parsed.skipped} 行。请检查日志格式。`;
        return;
      }
      result.className = 'parse-result';
      result.textContent = `解析预览：${parsed.totalLines} 行 → ${parsed.events.length} 条事件，跳过 ${parsed.skipped} 行；覆盖 ${new Set(parsed.events.map((event) => event.moduleId)).size} 个模块。${parsed.errors.length ? ` 首个错误：第 ${parsed.errors[0].line} 行 ${parsed.errors[0].reason}。` : ''}`;
    }
    state.sourceLogs = text;
    state.sourceName = state.pendingLogName || 'imported_cockpit_diagnostic.log';
    state.pendingLogName = null;
    closeModal();
    startLogScan();
  }

  /* ============================================================
     8D report
     ============================================================ */

  function renderJinja(template, context) {
    let output = template;
    let guard = 0;
    while (guard < 200) {
      guard += 1;
      const opening = /\{%\s*for\s+(\w+)\s+in\s+([\w.]+)\s*%\}/.exec(output);
      if (!opening) break;
      const bodyStart = opening.index + opening[0].length;
      const tagPattern = /\{%\s*(for|endfor)\b[^%]*%\}/g;
      tagPattern.lastIndex = bodyStart;
      let depth = 1;
      let close = null;
      let match;
      while ((match = tagPattern.exec(output))) {
        if (match[1] === 'for') depth += 1;
        else {
          depth -= 1;
          if (depth === 0) {
            close = { start: match.index, end: tagPattern.lastIndex };
            break;
          }
        }
      }
      if (!close) break;
      const body = output.slice(bodyStart, close.start);
      const items = getPath(context, opening[2]) || [];
      const rendered = items.map((item) => renderJinja(body, { ...context, [opening[1]]: item })).join('');
      output = output.slice(0, opening.index) + rendered + output.slice(close.end);
    }
    return output.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (full, path) => {
      const value = getPath(context, path);
      return value == null ? '' : String(value);
    });
  }

  function createReportSnapshot(moduleId) {
    const canvas = document.createElement('canvas');
    canvas.width = 720;
    canvas.height = 250;
    const context = canvas.getContext('2d');
    if (!context) return '';
    drawMiniChart(context, 720, 250, moduleId, true);
    return canvas.toDataURL('image/png');
  }

  const JOINT_REPORT_META = {
    title: '8D 三域智能诊断维修分析报告',
    subtitle: 'Intelligent Cockpit Diagnostic Console · CDC / MDC / VDC · 自动诊断 / 日志关联 / 根因分析',
    appendix: 'CDC / MDC / VDC 三域模块异常事件时间轴'
  };

  function filterByDomain(list, keepCode) {
    if (!Array.isArray(list)) return list;
    const others = DOMAIN_ORDER
      .filter((id) => DOMAINS[id].code !== keepCode)
      .map((id) => DOMAINS[id].code);
    const kept = list.filter((item) => {
      const text = JSON.stringify(item);
      return !others.some((code) => text.includes(code));
    });
    return kept.length ? kept : list.slice(0, 1);
  }

  function scope8D(context) {
    if (state.view === 'joint') {
      return { ...context, report: { ...context.report, ...JOINT_REPORT_META } };
    }
    const meta = DOMAINS[state.domain] || DOMAINS.cdc;
    const summary = computeSummary(state.domain);
    const modules = (context.modules || []).filter((module) => module.domainCode === meta.code);
    const topEvents = (context.topEvents || []).filter((event) =>
      String(event.module || '').startsWith(meta.code)
    );
    return {
      ...context,
      modules,
      topEvents,
      containment: filterByDomain(context.containment, meta.code),
      corrective: filterByDomain(context.corrective, meta.code),
      prevention: filterByDomain(context.prevention, meta.code),
      rootCauses: filterByDomain(context.rootCauses, meta.code),
      correlations: filterByDomain(context.correlations, meta.code),
      validation: filterByDomain(context.validation, meta.code),
      team: filterByDomain(context.team, meta.code),
      report: {
        ...context.report,
        id: `${context.report.id}-${meta.code}`,
        model: `NEXUS E7 · ${meta.code}`,
        title: `8D ${meta.name}维修分析报告`,
        subtitle: `Intelligent Cockpit Diagnostic Console · ${meta.code} 单域 · 自动诊断 / 日志关联 / 根因分析`,
        appendix: `${meta.name}模块异常事件时间轴`,
        summary:
          `本次诊断范围为 ${meta.name}（${meta.code}）单域：覆盖 ${modules.length} 个模块，` +
          `命中 ${summary.anomalies} 条异常（${summary.critical} 严重 / ${summary.warning} 警告），` +
          `域健康分 ${fmt(summary.health, 1)}。其余两域本机外设未接入，报告只包含本域数据；` +
          `如需跨域结论，请先切换到「三域联合诊断」再导出。`
      }
    };
  }

  function enterJoint() {
    state.view = 'joint';
    state.activeModule = null;
    state.eventFilter = 'anomaly';
    try {
      window.history.pushState(null, '', '#/joint');
    } catch (error) {
      window.location.hash = '#/joint';
    }
    renderAll();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderJointOverview() {
    const main = $('#mainContent');
    if (!main) return;
    const globalSummary = state.globalSummary || computeSummary(null);
    const rows = state.modules.flatMap((module) => {
      const domain = DOMAINS[module.domain];
      return getModuleState(module).events
        .filter((event) => event.severity !== 'info')
        .map((event) => ({ ...event, domainCode: domain.code, color: domain.color, moduleName: module.name }));
    }).sort((a, b) => (b.severity === 'critical') - (a.severity === 'critical') || b.timestamp - a.timestamp);

    const cards = DOMAIN_ORDER.map((id) => {
      const meta = DOMAINS[id];
      const summary = computeSummary(id);
      const count = state.modules.filter((module) => module.domain === id).length;
      return `<button type="button" data-domain="${id}" style="flex:1;min-width:170px;text-align:left;cursor:pointer;border:1px solid rgba(255,255,255,.09);border-left:3px solid ${meta.color};border-radius:10px;background:rgba(255,255,255,.03);padding:12px 14px;color:inherit">
        <div style="font:600 11px/1 Consolas,monospace;color:${meta.color};letter-spacing:.08em">${meta.code}</div>
        <div style="margin-top:6px;font-size:14px;font-weight:600">${meta.name}</div>
        <div style="margin-top:4px;font-size:11px;opacity:.7">${count} 模块 · ${summary.anomalies} 条异常</div>
        <div style="margin-top:8px;font:600 22px/1 Consolas,monospace;color:${meta.color}">${fmt(summary.health, 1)}<span style="font-size:11px;opacity:.6"> /100</span></div>
      </button>`;
    }).join('');

    const list = rows.slice(0, 14).map((event) => `
      <tr style="border-bottom:1px solid rgba(255,255,255,.06)">
        <td style="padding:7px 10px;font:500 11px/1.4 Consolas,monospace;opacity:.75;white-space:nowrap">${event.time.slice(0, 8)}</td>
        <td style="padding:7px 10px;white-space:nowrap"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${event.color};margin-right:6px"></span>${event.domainCode}</td>
        <td style="padding:7px 10px;opacity:.85">${escapeHtml(event.moduleName)}</td>
        <td style="padding:7px 10px">${escapeHtml(event.title)}</td>
        <td style="padding:7px 10px;white-space:nowrap"><span style="font-size:10px;padding:2px 7px;border-radius:99px;background:${event.severity === 'critical' ? 'rgba(217,74,74,.18)' : 'rgba(232,163,61,.18)'};color:${event.severity === 'critical' ? '#ff8d8d' : '#f0c27b'}">${event.severityLabel}</span></td>
      </tr>`).join('');

    main.innerHTML = `
      <div class="page-head">
        <div>
          <span class="eyebrow">CROSS-DOMAIN · JOINT DIAGNOSIS WORKSPACE</span>
          <h1>三域联合诊断总览</h1>
          <p class="page-sub">CDC + MDC + VDC 统一时间轴 · ${state.modules.length} 个模块 · ${globalSummary.anomalies} 条异常 · 8D 报告覆盖全部三域</p>
        </div>
        <div style="text-align:right;white-space:nowrap">
          <div style="font:600 10px/1 Consolas,monospace;opacity:.6;letter-spacing:.1em">JOINT HEALTH</div>
          <div style="margin-top:6px;font:600 30px/1 Consolas,monospace">${fmt(globalSummary.health, 1)}</div>
        </div>
      </div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 22px">${cards}</div>
      <section style="border:1px solid rgba(255,255,255,.09);border-radius:12px;overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.08)">
          <b style="font-size:13px">跨域异常时间轴</b>
          <span style="font-size:11px;opacity:.6">严重度优先 · 前 14 条 · 共 ${rows.length} 条</span>
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:12px"><tbody>${list}</tbody></table>
      </section>
    `;
  }

  function build8DContext() {
    const summary = state.globalSummary || computeSummary(null);
    const allAnomalies = state.modules
      .flatMap((module) => {
        const domain = DOMAINS[module.domain];
        const cleanName = module.name.replace(new RegExp(`^${domain.code}\\s*`), '');
        return getModuleState(module).events
          .filter((event) => event.severity !== 'info')
          .map((event) => ({
            ...event,
            moduleName: `${domain.code} · ${cleanName}`,
            moduleColor: module.color,
            domainCode: domain.code
          }));
      })
      .sort((first, second) => {
        const weight = { critical: 2, warning: 1 };
        return (weight[second.severity] - weight[first.severity]) || (second.timestamp - first.timestamp);
      });
    const topEvents = allAnomalies.slice(0, 8).map((event) => ({
      time: event.time.slice(0, 8),
      module: event.moduleName,
      title: escapeHtml(event.title),
      detail: escapeHtml(event.detail),
      severity: event.severity,
      severityLabel: event.severityLabel
    }));
    const top = allAnomalies[0];

    const team = [
      { name: '林工', initials: 'LG', role: '诊断系统工程师', duty: '日志解析、跨域证据链、8D 主笔' },
      { name: '周工', initials: 'ZG', role: 'SOC / 内核专家', duty: 'CDC / MDC SoC 欠压、ECC、DDR 时序' },
      { name: '陈工', initials: 'CG', role: '感知 / 显示专家', duty: 'Camera、LiDAR、SerDes、感知时延' },
      { name: '王工', initials: 'WG', role: '质量 / 可靠性', duty: '遏制措施、回归验证与预防机制' },
      { name: '赵工', initials: 'ZHAO', role: 'MDC 规控专家', duty: 'AI 算力、锁步安全岛、MDC 网络与功耗' },
      { name: '钱工', initials: 'QIAN', role: 'VDC 车控专家', duty: '车控 SoC、CAN/LIN、电源与底盘接口' }
    ];

    const containment = [
      { index: '01', action: '将 CPU3 所属簇最高频点下调一档，限制 GPU 峰值负载至 70%，观察 30 分钟。', owner: 'CDC SOC 组 / 周工', due: '今日 12:00', status: '已执行' },
      { index: '02', action: '对前视摄像头启用 24 FPS 降级与毫米波雷达融合冗余，避免 NOA 功能中断。', owner: 'MDC 感知组 / 陈工', due: '今日 12:10', status: '已执行' },
      { index: '03', action: '切换 5G 主天线至分集天线，暂停 n78 高频段业务并安排线束阻抗复测。', owner: '射频组 / 王工', due: '今日 12:30', status: '执行中' },
      { index: '04', action: '对 UFS 坏块执行重映射，迁移高风险冷数据并保留 4 个预留块。', owner: '存储组 / 林工', due: '今日 14:00', status: '待执行' },
      { index: '05', action: '提高 CDC / MDC 风扇占空比，将 SoC 封装温度控制在 78°C 以下。', owner: '热管理组 / 周工', due: '立即', status: '已执行' },
      { index: '06', action: '冻结 MDC 锁步 mismatch 现场，安全岛保持降级运行并限制 L2+ 激活。', owner: 'MDC 安全组 / 赵工', due: '立即', status: '执行中' },
      { index: '07', action: '限制 CAN FD 0 非关键报文，复核右后门 LIN 接插件与 12V 瞬态。', owner: 'VDC 车控组 / 钱工', due: '今日 13:00', status: '执行中' },
      { index: '08', action: '暂停 VDC OTA 下载，待 12V 电压稳定且 U0100 清除后继续。', owner: '平台组 / 林工', due: '立即', status: '已执行' }
    ];

    const rootCauses = [
      { why: 'WHY 1', answer: ' CDC CPU3 发生 0.71V 欠压瞬态，PMIC VCORE 余量在负载跳变时不足。' },
      { why: 'WHY 2', answer: ' GPU/NPU 并发峰值与 DDR CH2 占用跳变叠加，形成 68.1W 瞬态尖峰。' },
      { why: 'WHY 3', answer: ' MDC NPU0 热降频与 BEV 模型加载 128ms 叠加，导致感知时延升至 48ms。' },
      { why: 'WHY 4', answer: ' MDC 锁步核 mismatch 与 ETH2 丢包同窗口，安全岛接管降级链路。' },
      { why: 'WHY 5', answer: ' VDC 12V 瞬态跌落触发 U0100 与异常复位，CAN FD 0 负载放大通信风险。' }
    ];

    const correlations = [
      { title: 'CDC 功率—温度—欠压同窗', detail: '10:32:14 CPU3 欠压 → 10:32:17 VCORE 68.1W 尖峰 → 温升 84°C，时序高度重合。' },
      { title: 'DDR CH2 与帧缓冲', detail: 'CH2 BANK7 占用 91.2%、跳变 18.4%，与 Camera 掉帧、SerDes 重训练同窗口。' },
      { title: 'MDC 算力—感知链路', detail: 'NPU0 86°C 热降频后，BEV 模型加载 128ms，前视 Camera 时延升至 48ms。' },
      { title: 'VDC 电源—通信—复位', detail: '12V 跌至 11.72V → U0100/CAN 高负载 → VDC 异常复位，形成完整因果链。' }
    ];

    const corrective = [
      { action: 'PMIC VCORE 瞬态补偿 +20mV，更新 CPU3 簇电压/频率联动表', owner: '周工 / CDC SOC', due: '10-28', validation: '12 核满载 + GPU/NPU 并发 2h 压力测试' },
      { action: '将 Camera 帧缓冲迁移至 DDR CH0/CH1，设置 CH2 带宽上限', owner: '林工 / 平台', due: '10-29', validation: '4 路摄像头 4K 连续录制 2h，无掉帧' },
      { action: 'MDC BEV 队列双 NPU 均衡调度，限制 NPU0 温度墙 80°C', owner: '赵工 / MDC', due: '10-30', validation: 'BEV + Planning 混合负载 2h' },
      { action: '修复 MDC 锁步比较器与 ETH2 跨域丢包，复核 TSN 调度', owner: '赵工 / MDC', due: '11-01', validation: '锁步 0 mismatch，ETH2 丢包 < 0.1%' },
      { action: '更换主天线线束并复测 VSWR < 2.0、阻抗 < 5Ω', owner: '王工 / 射频', due: '10-27', validation: '全频段天线自检 + 5G 路测' },
      { action: 'UFS 固件升级，扩展坏块预留区并调整写入放大策略', owner: '林工 / 存储', due: '11-02', validation: '全盘扫描 2 轮 + P99 延迟 < 40ms' },
      { action: 'VDC 12V 瞬态抑制与 CAN 限流，复核右后门 LIN 终端', owner: '钱工 / VDC', due: '10-31', validation: '冷启动 50 次 + CAN 负载 < 65%' }
    ];

    const validation = [
      { item: 'CDC SoC 电压稳定性', method: '12 核 + GPU + NPU 满载 2h', criteria: 'VDD 最低 ≥ 0.75V，无欠压保护', result: '待验证', resultClass: 'info' },
      { item: 'DDR 带宽与 ECC', method: '4 路 4K 摄像头 + AI 推理', criteria: 'CH2 占用 < 85%，UE = 0', result: '待验证', resultClass: 'info' },
      { item: 'MDC 算力与感知', method: 'BEV + Planning 混合负载 2h', criteria: 'NPU < 80°C，Camera < 35ms', result: '待验证', resultClass: 'info' },
      { item: 'MDC 安全与 TSN', method: '锁步注入 + ETH2 丢包测试', criteria: '0 mismatch，丢包 < 0.1%', result: '待验证', resultClass: 'info' },
      { item: 'VDC 电源与通信', method: '冷启动 50 次 + CAN 满载', criteria: '12V ≥ 11.8V，0 U0100', result: '待验证', resultClass: 'info' },
      { item: '稳定性回归', method: '三域 Monkey 12h + 异常重启注入', criteria: '0 panic / 0 ANR', result: '待验证', resultClass: 'info' }
    ];

    const prevention = [
      { index: '01', item: '将 CDC CPU3 欠压、L2 ECC、VCORE 尖峰加入联合监控规则', owner: '平台组', detail: '同一 500ms 窗口出现任意两项即触发预警。' },
      { index: '02', item: 'DDR 日志解析器增加容量 / CH / BANK 自动匹配', owner: '诊断组', detail: '根据容量型号加载 8/16 BANK 映射，避免误判。' },
      { index: '03', item: 'MDC NPU 温度、感知时延、ETH2 丢包建立跨域门限', owner: 'MDC 组', detail: '任一指标越限即冻结 BEV 现场并降级 L2+。' },
      { index: '04', item: 'VDC 12V 瞬态、CAN 负载、U0100 联动监控', owner: 'VDC 组', detail: '电压跌落与 DTC 同时出现时自动暂停 OTA。' },
      { index: '05', item: '8D 报告纳入三域模块异常时间轴与图表快照', owner: '质量组', detail: '每次 OTA 前强制归档全域健康检查。' }
    ];

    const modules = state.modules.map((module) => {
      const moduleState = getModuleState(module);
      const events = moduleState.events
        .filter((event) => event.severity !== 'info')
        .map((event) => ({
          time: event.time.slice(0, 8),
          title: escapeHtml(event.title),
          detail: escapeHtml(event.detail),
          severity: event.severity,
          severityLabel: event.severityLabel
        }));
      return {
        index: module.index,
        domainCode: DOMAINS[module.domain].code,
        domainName: escapeHtml(DOMAINS[module.domain].name),
        name: escapeHtml(module.name),
        subtitle: escapeHtml(module.subtitle),
        health: fmt(moduleState.health, 1),
        statusLabel: moduleState.statusLabel,
        eventCount: moduleState.anomalies,
        critical: moduleState.critical,
        warning: moduleState.warning,
        summary: escapeHtml(moduleState.summary),
        events,
        chart: createReportSnapshot(module.id),
        chartCaption: escapeHtml(module.chartCaption)
      };
    });

    const anomalyText = summary.anomalies
      ? `共命中 ${summary.anomalies} 条异常，其中 ${summary.critical} 条严重、${summary.warning} 条警告。${top ? `最高优先级为 ${top.moduleName} 的「${top.title}」。` : ''}`
      : '未发现严重异常。';

    return {
      report: {
        id: `8D-${new Date().getFullYear()}${pad2(new Date().getMonth() + 1)}${pad2(new Date().getDate())}-${pad2(new Date().getHours())}${pad2(new Date().getMinutes())}`,
        date: formatDate(new Date()),
        software: 'COCKPIT OS · DIAG v2.5',
        vin: 'LNAX7E4W2R0018462',
        model: 'NEXUS E7 · CDC / MDC / VDC',
        statusLabel: summary.statusLabel,
        summary: escapeHtml(`本次日志扫描覆盖 ${summary.logLines} 行、${summary.moduleCount} 个诊断模块（CDC / MDC / VDC）。${anomalyText} 跨域证据链显示：CDC CPU 欠压 / DDR 跳变 / 功耗尖峰构成第一组风险，MDC NPU 热降频 / Camera 时延 / 锁步 mismatch 构成第二组风险，VDC 12V 瞬态 / CAN 高负载 / 异常复位构成第三组风险。`)
      },
      summary: {
        health: fmt(summary.health, 1),
        anomalies: summary.anomalies,
        critical: summary.critical,
        warning: summary.warning,
        modulesAffected: summary.modulesAffected,
        moduleCount: summary.moduleCount,
        logLines: fmtInt(summary.logLines),
        totalEvents: state.parsed.events.length
      },
      team,
      topEvents,
      d2Narrative: escapeHtml(`车辆在正常上电后，诊断系统扫描 CDC / MDC / VDC 三域日志并完成 ${summary.moduleCount} 个模块映射。${anomalyText} 异常主要集中在上电后 10:31–10:39 的 8 分钟窗口内，且与实时监控中的 SoC 欠压、DDR 通道跳变、MDC NPU 热降频、Camera 时延和 VDC 12V 瞬态相互印证。`),
      containment,
      rootCauses,
      correlations,
      corrective,
      validation,
      prevention,
      d8Narrative: escapeHtml(`本次三域异常已完成遏制与证据固化，根因指向 CDC VCORE 瞬态余量、MDC 算力/感知链路稳定性以及 VDC 12V 电源与 CAN 通信耦合。永久措施将在 11 月 2 日前完成，并以 12 小时三域稳定性测试及全量模块回归作为关闭条件。 AI 诊断 Agent 与专项小组共同确认本报告。`),
      modules
    };
  }

  function export8DReport() {
    if (state.scanning) {
      toast('日志仍在扫描中，请稍后导出', 'warn');
      return;
    }
    if (!window.EIGHT_D_TEMPLATE) {
      toast('8D 模板未加载，无法生成报告', 'error');
      return;
    }
    const button = $('#exportBtn');
    if (button) {
      button.disabled = true;
      button.dataset.original = button.innerHTML;
      button.innerHTML = `${icon('refresh')}<span>正在生成 ${MODULE_DEFS.length} 模块快照…</span>`;
    }
    window.setTimeout(() => {
      try {
        const context = scope8D(build8DContext());
        let html = renderJinja(window.EIGHT_D_TEMPLATE, context);
        if (state.view !== 'joint') {
          const code = (DOMAINS[state.domain] || DOMAINS.cdc).code;
          html = html.replace(/CDC \/ MDC \/ VDC/g, code).replace(/CDC \/ MDC/g, code);
        }
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `NEXUS_COCKPIT_8D维修报告_${context.report.id.replace('8D-', '')}.html`;
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 3000);
        toast('8D 维修报告已导出 · 含 CDC / MDC / VDC 三域时间轴与图表快照');
      } catch (error) {
        console.error(error);
        toast('报告生成失败，请重试', 'error');
      } finally {
        if (button) {
          button.disabled = false;
          button.innerHTML = button.dataset.original || `${icon('download')}<span>一键导出维修报告</span>`;
          delete button.dataset.original;
        }
      }
    }, 60);
  }

  /* ============================================================
     Navigation / events
     ============================================================ */

  function navigate(view, moduleId = null) {
    if (view === 'module' && moduleId) {
      const module = MODULE_DEFS.find((item) => item.id === moduleId);
      if (module) {
        state.domain = module.domain;
        state.activeModule = moduleId;
      }
    }
    state.view = view;
    if (view !== 'module') state.activeModule = null;
    state.eventFilter = 'anomaly';
    const hash = view === 'module' && state.activeModule ? `#/module/${state.activeModule}` : `#/domain/${state.domain}`;
    if (window.location.hash !== hash) {
      try {
        window.history.pushState(null, '', hash);
      } catch (error) {
        window.location.hash = hash;
      }
    }
    renderAll();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $('#mainContent')?.focus({ preventScroll: true });
  }

  function navigateDomain(domain) {
    if (!DOMAINS[domain]) return;
    state.domain = domain;
    state.view = 'overview';
    state.activeModule = null;
    state.eventFilter = 'anomaly';
    const hash = `#/domain/${domain}`;
    if (window.location.hash !== hash) {
      try {
        window.history.pushState(null, '', hash);
      } catch (error) {
        window.location.hash = hash;
      }
    }
    renderAll();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function applyHashRoute() {
    const moduleMatch = window.location.hash.match(/^#\/module\/([a-z0-9-]+)$/);
    if (moduleMatch) {
      const module = MODULE_DEFS.find((item) => item.id === moduleMatch[1]);
      if (module) {
        state.domain = module.domain;
        state.view = 'module';
        state.activeModule = module.id;
        renderAll();
        return;
      }
    }
    if (window.location.hash === '#/joint') {
      state.view = 'joint';
      state.activeModule = null;
      renderAll();
      return;
    }
    const domainMatch = window.location.hash.match(/^#\/domain\/(cdc|mdc|vdc)$/);
    if (domainMatch) {
      state.domain = domainMatch[1];
      state.view = 'overview';
      state.activeModule = null;
      renderAll();
      return;
    }
    state.view = 'overview';
    state.activeModule = null;
    renderAll();
  }

  // ---------- 8D 报告导出：HTML / PPT 两种格式 ----------
  // 构建标记：控制台可见，用于确认浏览器加载的是最新脚本
  console.info('NEXUS COCKPIT build 20261028h · scoped-8d');

  function closeExportMenu() {
    const menu = document.getElementById('exportMenu');
    if (menu) menu.remove();
  }

  function openExportMenu(event) {
    if (event) event.stopPropagation();
    closeExportMenu();
    const button = $('#exportBtn');
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const itemStyle =
      'display:block;width:100%;padding:9px 12px;border:0;border-radius:7px;' +
      'background:transparent;color:#e6edf7;font-size:13px;text-align:left;cursor:pointer';
    const menu = document.createElement('div');
    menu.id = 'exportMenu';
    menu.style.cssText =
      'position:fixed;z-index:9999;width:226px;padding:6px;border-radius:10px;' +
      'background:#101826;border:1px solid #26324a;box-shadow:0 18px 45px rgba(0,0,0,.5);' +
      `top:${rect.bottom + 8}px;left:${Math.max(12, Math.min(rect.right - 226, window.innerWidth - 238))}px`;
    menu.innerHTML =
      `<button type="button" data-export="html" style="${itemStyle}">导出 HTML 维修报告</button>` +
      `<button type="button" data-export="ppt" style="${itemStyle}">导出 PPT 演示文稿（.pptx）</button>`;
    document.body.appendChild(menu);
    menu.addEventListener('click', (target) => {
      const choice = target.target.closest('[data-export]');
      if (!choice) return;
      const kind = choice.dataset.export;
      closeExportMenu();
      if (kind === 'ppt') exportPptReport();
      else export8DReport();
    });
    setTimeout(() => document.addEventListener('click', closeExportMenu, { once: true }), 0);
  }

  const PPT_LABELS = {
    index: '#', why: 'Why', item: '项目', action: '措施', title: '标题', detail: '说明',
    method: '方法', owner: '责任人', due: '完成节点', criteria: '验收标准', result: '结果',
    status: '状态', answer: '答案', validation: '验证方式', phase: '阶段'
  };

  function pptTabulate(list) {
    if (!Array.isArray(list) || list.length === 0) return null;
    const keys = Object.keys(list[0]).filter(
      (key) => typeof list[0][key] !== 'object' && PPT_LABELS[key]
    );
    if (keys.length === 0) return null;
    return {
      headers: keys.map((key) => PPT_LABELS[key]),
      rows: list.map((entry) => keys.map((key) => String(entry[key] ?? '')))
    };
  }

  function exportPptReport() {
    if (typeof PptxGenJS === 'undefined') {
      toast('PPT 组件未加载，请检查 vendor/pptxgen.bundle.js', 'error');
      return;
    }
    const button = $('#exportBtn');
    const original = button ? button.innerHTML : '';
    if (button) button.innerHTML = '<span>正在生成 PPT…</span>';

    try {
      const ctx = scope8D(build8DContext());
      const pptx = new PptxGenJS();
      pptx.layout = 'LAYOUT_16x9';
      pptx.author = 'NEXUS COCKPIT';
      pptx.title = `8D 维修分析报告 ${ctx.report.id}`;

      const C = {
        navy: '0B1020', ink: '14233A', muted: '6B7A90', bg: 'F5F7FB', accent: '2C5F9E',
        blue: '4C8DFF', cyan: '22D3EE', lime: 'A3E635', red: 'D94A4A', amber: 'E8A33D',
        green: '3BA776', line: 'D8E0EA'
      };
      const FONT = 'Microsoft YaHei';
      const W = 10;
      const M = 0.45;

      const page = (eyebrow, title, num) => {
        const s = pptx.addSlide();
        s.background = { color: C.bg };
        s.addShape('rect', { x: 0, y: 0, w: W, h: 0.05, fill: { color: C.navy } });
        s.addText(eyebrow, { x: M, y: 0.26, w: 7, h: 0.22, fontSize: 8, color: C.accent, bold: true, fontFace: 'Consolas' });
        s.addText(title, { x: M, y: 0.44, w: W - 1.3, h: 0.42, fontSize: 19, color: C.ink, bold: true, fontFace: FONT });
        s.addShape('rect', { x: M, y: 0.92, w: 0.78, h: 0.035, fill: { color: C.blue } });
        s.addText(String(num).padStart(2, '0'), { x: W - 0.95, y: 0.28, w: 0.5, h: 0.2, fontSize: 8, color: C.muted, align: 'right', fontFace: 'Consolas' });
        return s;
      };

      const table = (s, headers, rows, y, colW, fontSize = 8) => {
        const head = headers.map((label) => ({
          text: label,
          options: { bold: true, color: 'FFFFFF', fill: { color: C.navy }, fontSize }
        }));
        const body = rows.map((row) =>
          row.map((cell) => ({ text: cell, options: { fontSize, color: C.ink } }))
        );
        s.addTable([head, ...body], {
          x: M, y, w: W - 2 * M, colW,
          border: { type: 'solid', pt: 0.5, color: C.line },
          fontFace: FONT, valign: 'middle', autoPage: false
        });
      };

      // 01 封面
      const cover = pptx.addSlide();
      cover.background = { color: C.navy };
      cover.addShape('rect', { x: 0, y: 0, w: 0.08, h: 5.625, fill: { color: C.blue } });
      cover.addText('8D PROBLEM SOLVING REPORT', { x: 0.7, y: 1.1, w: 7, h: 0.25, fontSize: 9, color: C.cyan, bold: true, fontFace: 'Consolas' });
      cover.addText('8D 维修分析报告', { x: 0.7, y: 1.42, w: 8, h: 0.8, fontSize: 34, color: 'FFFFFF', bold: true, fontFace: FONT });
      cover.addText('智能座舱域控制器 · 三域联合诊断', { x: 0.7, y: 2.24, w: 8, h: 0.3, fontSize: 13, color: 'C7D3E3', fontFace: FONT });
      cover.addShape('rect', { x: 0.72, y: 2.7, w: 1.1, h: 0.035, fill: { color: C.cyan } });
      const meta = [
        ['报告编号', ctx.report.id],
        ['车型 / 样机', ctx.report.model],
        ['软件版本', ctx.report.software],
        ['编制日期', ctx.report.date]
      ];
      meta.forEach((pair, i) => {
        cover.addText(pair[0], { x: 0.72, y: 3.0 + i * 0.34, w: 1.4, h: 0.25, fontSize: 8.5, color: '7F92AD', fontFace: 'Consolas' });
        cover.addText(String(pair[1]), { x: 2.1, y: 3.0 + i * 0.34, w: 5, h: 0.25, fontSize: 10, color: 'FFFFFF', fontFace: FONT });
      });
      cover.addText('由 CDC / MDC / VDC 三域诊断日志自动生成，数据可回溯至原始日志行。',
        { x: 0.7, y: 4.9, w: 8.5, h: 0.25, fontSize: 8, color: '6F8099', fontFace: FONT });

      // 02 摘要
      const summary = state.globalSummary || computeSummary(null);
      const s2 = page('EXECUTIVE SUMMARY', '执行摘要', 2);
      const kpis = [
        [summary.anomalies ?? 0, '异常事件', C.blue],
        [summary.critical ?? 0, '严重', C.red],
        [summary.warning ?? 0, '警告', C.amber],
        [summary.modules ?? 23, '涉及模块', C.accent]
      ];
      kpis.forEach((kpi, i) => {
        const x = M + i * 2.28;
        s2.addShape('rect', { x, y: 1.2, w: 2.08, h: 0.92, fill: { color: 'FFFFFF' }, line: { color: C.line, pt: 0.75 } });
        s2.addShape('rect', { x, y: 1.2, w: 0.05, h: 0.92, fill: { color: kpi[2] } });
        s2.addText(String(kpi[0]), { x: x + 0.16, y: 1.3, w: 1.6, h: 0.42, fontSize: 22, bold: true, color: kpi[2], fontFace: 'Consolas' });
        s2.addText(kpi[1], { x: x + 0.16, y: 1.78, w: 1.6, h: 0.24, fontSize: 8.5, color: C.muted, fontFace: FONT });
      });
      s2.addText('首要结论', { x: M, y: 2.4, w: 3, h: 0.25, fontSize: 10, bold: true, color: C.red, fontFace: FONT });
      s2.addText(ctx.report.summary || '', { x: M, y: 2.68, w: W - 2 * M, h: 2.2, fontSize: 9.5, color: C.ink, fontFace: FONT, lineSpacingMultiple: 1.35, valign: 'top' });

      // 03 D1
      const s3 = page('D1 · TEAM', 'D1 成立专项小组', 3);
      table(s3,
        ['成员', '角色', '职责'],
        ctx.team.map((m) => [m.name, m.role, m.duty]),
        1.15, [1.2, 2.0, 5.9], 8.5);

      // 04 D2
      const s4 = page('D2 · PROBLEM', 'D2 问题描述：异常事件 TOP', 4);
      table(s4,
        ['时间', '模块', '事件', '级别'],
        ctx.topEvents.slice(0, 6).map((e) => [e.time, e.module, e.title, e.severityLabel]),
        1.15, [0.85, 2.1, 4.6, 1.0], 7.5);

      // 05-09 D3..D7
      const sections = [
        ['D3 · CONTAINMENT', 'D3 临时遏制措施', ctx.containment, 5],
        ['D4 · ROOT CAUSE', 'D4 根本原因分析', ctx.rootCauses, 6],
        ['D5 · CORRECTIVE', 'D5 永久纠正措施', ctx.corrective, 7],
        ['D6 · VALIDATION', 'D6 实施与验证', ctx.validation, 8],
        ['D7 · PREVENTION', 'D7 预防再发生', ctx.prevention, 9]
      ];
      sections.forEach((section) => {
        const [, title, data, num] = section;
        const s = page(section[0], title, num);
        const tab = pptTabulate(data);
        if (!tab) {
          s.addText('本版本无该阶段条目。', { x: M, y: 1.3, w: 8, h: 0.3, fontSize: 10, color: C.muted, fontFace: FONT });
          return;
        }
        const widths = tab.headers.map(() => (W - 2 * M) / tab.headers.length);
        table(s, tab.headers, tab.rows, 1.15, widths, tab.rows.length > 4 ? 7 : 8);
      });

      // 10 D8
      const s10 = page('D8 · CLOSURE', 'D8 小组认可与关闭', 10);
      s10.addText(ctx.report.statusLabel || '已关闭', { x: M, y: 1.2, w: 3, h: 0.4, fontSize: 18, bold: true, color: C.green, fontFace: FONT });
      s10.addText('质量负责人 ___________    维修负责人 ___________    日期 ' + ctx.report.date,
        { x: M, y: 2.0, w: W - 2 * M, h: 0.3, fontSize: 9, color: C.muted, fontFace: FONT });

      // 11 附录：23 模块
      const s11 = page('APPENDIX', '附件：模块健康分与异常分布', 11);
      const half = Math.ceil(ctx.modules.length / 2);
      [ctx.modules.slice(0, half), ctx.modules.slice(half)].forEach((group, gi) => {
        const head = ['#', '模块', '域', '健康分', '异常'];
        const body = group.map((m) => [
          m.index, String(m.name), m.domainCode, String(m.health), String((m.events || []).length)
        ]);
        const x = M + gi * 4.6;
        const headCells = head.map((label) => ({
          text: label, options: { bold: true, color: 'FFFFFF', fill: { color: C.navy }, fontSize: 6.5 }
        }));
        const rows = body.map((row) => row.map((cell) => ({ text: cell, options: { fontSize: 6.5, color: C.ink } })));
        s11.addTable([headCells, ...rows], {
          x, y: 1.1, w: 4.4, colW: [0.4, 2.0, 0.55, 0.75, 0.6],
          border: { type: 'solid', pt: 0.5, color: C.line }, fontFace: FONT, valign: 'middle', autoPage: false
        });
      });

      const fileName = `NEXUS_COCKPIT_8D维修报告_${ctx.report.id.replace('8D-', '')}.pptx`;
      pptx.writeFile({ fileName }).then(() => {
        if (button) button.innerHTML = original;
        toast('PPT 已生成：' + fileName, 'success');
      }).catch((error) => {
        if (button) button.innerHTML = original;
        toast('PPT 生成失败：' + error.message, 'error');
      });
    } catch (error) {
      if (button) button.innerHTML = original;
      toast('PPT 生成失败：' + error.message, 'error');
    }
  }

  function bindEvents() {
    $('#themeToggle')?.addEventListener('click', () => {
      applyTheme(state.theme === 'dark' ? 'light' : 'dark');
      toast(state.theme === 'light' ? '已切换至白色主题' : '已切换至深色主题');
    });

    $('#logImportBtn')?.addEventListener('click', openLogModal);
    $('#rescanBtn')?.addEventListener('click', () => {
      if (state.scanning) return;
      startLogScan();
    });
    $('#exportBtn')?.addEventListener('click', openExportMenu);

    document.addEventListener('click', (event) => {
      const jointButton = event.target.closest('[data-joint]');
      if (jointButton) {
        enterJoint();
        return;
      }
      const domainButton = event.target.closest('[data-domain]');
      if (domainButton) {
        navigateDomain(domainButton.dataset.domain);
        return;
      }
      const moduleButton = event.target.closest('[data-module]');
      if (moduleButton) {
        navigate('module', moduleButton.dataset.module);
        return;
      }
      const viewButton = event.target.closest('[data-view]');
      if (viewButton) {
        navigate('overview');
        return;
      }
      const openModule = event.target.closest('[data-open-module]');
      if (openModule) {
        navigate('module', openModule.dataset.openModule);
        return;
      }
      const filter = event.target.closest('[data-event-filter]');
      if (filter) {
        state.eventFilter = filter.dataset.eventFilter;
        renderTimelineOnly();
        return;
      }
      const capacity = event.target.closest('[data-capacity]');
      if (capacity) {
        state.ddrCapacity = capacity.dataset.capacity;
        state.live.ddr.capacity = state.ddrCapacity;
        renderView();
        updateLiveLabels();
        return;
      }
      const action = event.target.closest('[data-action]');
      if (action) {
        handleAction(action.dataset.action);
      }
    });

    $('#modalRoot')?.addEventListener('click', (event) => {
      if (event.target === $('#modalRoot')) {
        closeModal();
        return;
      }
      const action = event.target.closest('[data-action]');
      if (action) {
        if (action.dataset.action === 'close-modal') {
          closeModal();
        } else if (action.dataset.action === 'load-sample') {
          const textarea = $('#logInput');
          if (textarea) textarea.value = SAMPLE_LOG;
          state.pendingLogName = 'cockpit_diagnostic_20261024.log';
          setText('#logFileName', `当前：cockpit_diagnostic_20261024.log · ${fmtInt(SAMPLE_LOG.length)} chars`);
          toast('示例日志已载入');
        } else if (action.dataset.action === 'parse-log') {
          validateAndLoadLog();
        }
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && $('#modalRoot')?.classList.contains('open')) closeModal();
    });

    window.addEventListener('hashchange', applyHashRoute);
    window.addEventListener('popstate', applyHashRoute);
  }

  function handleAction(action) {
    if (action === 'import-log') openLogModal();
    if (action === 'close-modal') closeModal();
    if (action === 'export-report') export8DReport();
    if (action === 'rescan') {
      if (!state.scanning) startLogScan();
    }
  }

  /* ============================================================
     Init
     ============================================================ */

  function init() {
    applyTheme(state.theme);
    state.globalSummary = computeSummary(null);
    state.summary = computeSummary('cdc');
    renderHeaderStatus();
    renderSidebar();
    const initialHash = window.location.hash;
    const moduleMatch = initialHash.match(/^#\/module\/([a-z0-9-]+)$/);
    if (moduleMatch) {
      const module = MODULE_DEFS.find((item) => item.id === moduleMatch[1]);
      if (module) {
        state.domain = module.domain;
        state.view = 'module';
        state.activeModule = module.id;
      }
    } else {
      const domainMatch = initialHash.match(/^#\/domain\/(cdc|mdc|vdc)$/);
      if (domainMatch) state.domain = domainMatch[1];
    }
    state.summary = computeSummary(state.domain);
    renderView();
    bindEvents();
    window.requestAnimationFrame(chartLoop);
    window.setInterval(updateTelemetry, 500);
    window.setTimeout(() => {
      startLogScan({ announce: false });
    }, 200);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
