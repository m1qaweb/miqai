const fetch = require("node-fetch");

/**
 * Performs a web search using the SearxNG service.
 * @param {string} query The search query.
 * @returns {Promise<string[]>} A promise that resolves to an array of URLs.
 */
async function webSearch(query) {
  const searxngUrl = `http://localhost:8888/search?q=${encodeURIComponent(
    query
  )}&format=json`;
  try {
    const response = await fetch(searxngUrl);
    const data = await response.json();
    return data.results.map((result) => result.url);
  } catch (error) {
    console.error("Error searching:", error);
    return [];
  }
}

/**
 * Fetches the cleaned text of a given URL using the fetcher service.
 * @param {string} url The URL to fetch.
 * @returns {Promise<string>} A promise that resolves to the cleaned text.
 */
async function fetchText(url) {
  const fetcherUrl = `http://localhost:8889/fetch?url=${encodeURIComponent(
    url
  )}`;
  try {
    const response = await fetch(fetcherUrl);
    const data = await response.json();
    return data.cleaned_text;
  } catch (error) {
    console.error(`Error fetching ${url}:`, error);
    return `Failed to fetch content from ${url}.`;
  }
}

/**
 * Orchestrates the search and fetch process.
 * @param {string} query The search query.
 * @returns {Promise<string>} A promise that resolves to the combined search results.
 */
async function handleSearchCommand(query) {
  const urls = await webSearch(query);
  if (!urls || urls.length === 0) {
    return "No search results found.";
  }

  const topUrls = urls.slice(0, 3);
  const fetchPromises = topUrls.map((url) => fetchText(url));
  const texts = await Promise.all(fetchPromises);

  let combinedResult = "";
  texts.forEach((text, index) => {
    combinedResult += `--- Source ${index + 1}: ${topUrls[index]} ---\n`;
    combinedResult += `${text}\n\n`;
  });

  return combinedResult.trim();
}

module.exports = { handleSearchCommand };
