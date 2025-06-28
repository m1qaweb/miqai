# Web Assistant Integration Logic

This module provides a simple interface to perform web searches and fetch cleaned text from the top results.

## Usage

```javascript
const { handleSearchCommand } = require("./index");

async function runSearch() {
  const results = await handleSearchCommand("your search query");
  console.log(results);
}

runSearch();
```
