/* ========================================
   站内搜索
   - 优先使用构建后生成的 Pagefind 索引
   - 索引不可用时回退到内嵌文章摘要
   ======================================== */

(function() {
  'use strict';

  var searchRoot = document.getElementById('search');
  var searchInput = document.getElementById('search-input');
  var searchResults = document.getElementById('search-results');
  var searchData = document.getElementById('search-data');

  if (!searchRoot || !searchInput || !searchResults) {
    return;
  }

  var pagefindUrl = searchRoot.getAttribute('data-pagefind-url');
  var pagefindPromise = null;
  var searchTimer = null;
  var latestRequest = 0;
  var fallbackPosts = [];

  if (searchData) {
    try {
      fallbackPosts = JSON.parse(searchData.textContent);
    } catch (error) {
      fallbackPosts = [];
    }
  }

  function loadPagefind() {
    if (pagefindPromise) {
      return pagefindPromise;
    }

    pagefindPromise = import(pagefindUrl)
      .then(async function(api) {
        if (typeof api.init === 'function') {
          await api.init();
        }
        return api;
      })
      .catch(function() {
        return null;
      });

    return pagefindPromise;
  }

  function setResultsVisible(visible) {
    searchResults.style.display = visible ? 'block' : 'none';
    searchInput.setAttribute('aria-expanded', String(visible));
  }

  function showEmptyState() {
    var message = document.createElement('p');
    message.className = 'no-results';
    message.textContent = '未找到相关情报';
    searchResults.replaceChildren(message);
    setResultsVisible(true);
  }

  function appendResult(fragment, result, allowMarkup) {
    var link = document.createElement('a');
    var title = document.createElement('span');
    var excerpt = document.createElement('span');

    link.className = 'search-result-item';
    link.href = result.url;

    title.className = 'result-title';
    title.textContent = result.title || '无标题';

    excerpt.className = 'result-excerpt';
    if (allowMarkup) {
      excerpt.innerHTML = result.excerpt || '';
    } else {
      excerpt.textContent = result.excerpt || '';
    }

    link.append(title, excerpt);
    fragment.appendChild(link);
  }

  function renderResults(results, allowMarkup) {
    if (!results.length) {
      showEmptyState();
      return;
    }

    var fragment = document.createDocumentFragment();
    results.forEach(function(result) {
      appendResult(fragment, result, allowMarkup);
    });
    searchResults.replaceChildren(fragment);
    setResultsVisible(true);
  }

  function searchFallback(query) {
    var normalizedQuery = query.toLocaleLowerCase('zh-CN');

    return fallbackPosts
      .filter(function(post) {
        var tags = Array.isArray(post.tags) ? post.tags.join(' ') : '';
        var searchable = [
          post.title,
          post.description,
          post.category,
          tags,
          post.business,
          post.content
        ].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN');

        return searchable.includes(normalizedQuery);
      })
      .slice(0, 8)
      .map(function(post) {
        return {
          title: post.title,
          url: post.url,
          excerpt: post.description || String(post.content || '').slice(0, 100)
        };
      });
  }

  async function runSearch(query, requestId) {
    var pagefind = await loadPagefind();

    if (requestId !== latestRequest) {
      return;
    }

    if (pagefind && typeof pagefind.search === 'function') {
      try {
        var response = await pagefind.search(query);
        var details = await Promise.all(
          response.results.slice(0, 8).map(function(result) {
            return result.data();
          })
        );

        if (requestId !== latestRequest) {
          return;
        }

        renderResults(details.map(function(result) {
          return {
            title: result.meta && result.meta.title,
            url: result.url,
            excerpt: result.excerpt
          };
        }), true);
        return;
      } catch (error) {
        // 索引加载失败时继续使用本地回退搜索
      }
    }

    renderResults(searchFallback(query), false);
  }

  searchInput.addEventListener('focus', loadPagefind, { once: true });

  searchInput.addEventListener('input', function() {
    window.clearTimeout(searchTimer);
    latestRequest += 1;

    var query = searchInput.value.trim();
    var requestId = latestRequest;

    if (!query) {
      searchResults.replaceChildren();
      setResultsVisible(false);
      return;
    }

    searchTimer = window.setTimeout(function() {
      runSearch(query, requestId);
    }, 220);
  });

  searchInput.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
      setResultsVisible(false);
      searchInput.blur();
    }
  });

  document.addEventListener('click', function(event) {
    if (!event.target.closest('#search')) {
      setResultsVisible(false);
    }
  });
})();
