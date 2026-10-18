export async function loadStock() {
  return fetch("https://stock.example/stock/123");
}

export async function renderOrder() {
  return loadStock();
}
