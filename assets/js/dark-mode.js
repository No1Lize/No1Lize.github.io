/* ========================================
   暗色模式切换脚本
   - 默认跟随系统偏好
   - 用户手动切换后记忆到 localStorage
   - 刷新后保持用户选择
   ======================================== */

(function() {
  'use strict';
  
  var TOGGLE_ID = 'theme-toggle';
  var STORAGE_KEY = 'theme';
  var systemThemeQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  // 获取用户手动保存的主题；存储不可用时安全降级
  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }
  
  // 保存用户手动选择的主题
  function storeTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      // 浏览器禁用本地存储时，当前页面仍可正常切换
    }
  }

  // 更新按钮状态和辅助说明
  function updateToggle(theme) {
    var btn = document.getElementById(TOGGLE_ID);
    if (!btn) {
      return;
    }

    var isDark = theme === 'dark';
    var label = isDark ? '切换为亮色模式' : '切换为暗色模式';
    btn.setAttribute('aria-pressed', String(isDark));
    btn.setAttribute('aria-label', label);
    btn.setAttribute('title', label);
  }

  // 应用主题；只有用户主动切换时才写入本地存储
  function applyTheme(theme, shouldStore) {
    document.documentElement.setAttribute('data-theme', theme);
    if (shouldStore) {
      storeTheme(theme);
    }
    updateToggle(theme);
  }
  
  // 获取系统偏好
  function getSystemTheme() {
    return systemThemeQuery.matches ? 'dark' : 'light';
  }
  
  // 初始化：优先用户保存值；否则跟随系统且不写入存储
  function initTheme() {
    var stored = getStoredTheme();
    if (stored === 'dark' || stored === 'light') {
      applyTheme(stored, false);
    } else {
      applyTheme(getSystemTheme(), false);
    }
  }
  
  // 切换主题
  function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next, true);
  }
  
  // 监听系统主题变化（仅当用户未手动设置时跟随）
  function watchSystemTheme() {
    var handleChange = function(e) {
      if (!getStoredTheme()) {
        applyTheme(e.matches ? 'dark' : 'light', false);
      }
    };

    if (systemThemeQuery.addEventListener) {
      systemThemeQuery.addEventListener('change', handleChange);
    } else if (systemThemeQuery.addListener) {
      systemThemeQuery.addListener(handleChange);
    }
  }
  
  // DOM 加载完成后绑定事件
  function bindEvents() {
    var btn = document.getElementById(TOGGLE_ID);
    if (btn) {
      btn.addEventListener('click', toggleTheme);
      updateToggle(document.documentElement.getAttribute('data-theme'));
    }
  }
  
  // 启动
  initTheme();
  watchSystemTheme();
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindEvents);
  } else {
    bindEvents();
  }
})();
