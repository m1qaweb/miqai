import express from "express";
import fetch from "node-fetch";
import cheerio from "cheerio";

const app = express();
const port = 8889;

/**
 * Fetches a URL and extracts the text content from all paragraph tags.
 * @param {string} url The URL to fetch.
 * @returns {Promise<string>} A promise that resolves to the extracted text.
 */
async function fetchText(url) {
  const res = await fetch(url);
  const html = await res.text();
  const $ = cheerio.load(html);
  // Grab all <p> tags
  return $("p")
    .map((_, p) => $(p).text())
    .get()
    .join("\n\n");
}

app.get("/fetch", async (req, res) => {
  const { url } = req.query;

  if (!url) {
    return res.status(400).send({ error: "URL query parameter is required" });
  }

  try {
    const text = await fetchText(url);
    res.type("text/plain").send(text);
  } catch (error) {
    console.error(`Error fetching URL: ${url}`, error);
    res.status(500).send({ error: "Failed to fetch or parse the URL" });
  }
});

app.listen(port, () => {
  console.log(`Fetcher service listening on port ${port}`);
});
