import { expect, test } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

test('real repository to affected endpoints, evidence, and export', async ({ page }) => {
  await page.goto('/');
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Analysis mode').selectOption('impact');
  await analysis.getByLabel('Repository path').fill(resolve('..', 'examples', 'commerce'));
  await analysis.getByLabel('Qualified targets').fill('inventory.validate_stock');
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByRole('button', { name: 'Export analysis JSON' })).toBeVisible();
  await analysis.getByText('Affected functions and endpoints', { exact: true }).click();
  await expect(analysis.getByText('POST /orders', { exact: true }).last()).toBeVisible();
  await expect(analysis.getByText('POST /reservations', { exact: true }).last()).toBeVisible();
  await analysis.getByRole('button', { name: 'orders.place_order', exact: true }).click();
  await expect(analysis.getByText(/explicit-python-binding-v1/).first()).toBeVisible();
  const download = page.waitForEvent('download');
  await analysis.getByRole('button', { name: 'Export analysis JSON' }).click();
  expect((await download).suggestedFilename()).toBe('repository-analysis.json');
});

test('proposal requires explicit confirmation and invalid path is visible', async ({ page }) => {
  await page.goto('/');
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Analysis mode').selectOption('propose');
  await analysis.getByLabel('Repository path').fill(resolve('..', 'examples', 'commerce'));
  await analysis.getByLabel('Describe the proposed change').fill('Change validate_stock');
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await analysis.getByRole('button', { name: 'Use inventory.validate_stock' }).click();
  await expect(analysis.getByRole('checkbox')).not.toBeChecked();
  await analysis.getByRole('checkbox').check();
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByText('Full analysis JSON')).toBeVisible();
  await analysis.getByLabel('Repository path').fill('no-such-repository');
  await expect(analysis.getByRole('checkbox')).not.toBeChecked();
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByRole('alert')).toBeVisible();
});


test('repository workflow excludes the old snapshot question and explains transport failure', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('Investigation question')).toHaveCount(0);
  await expect(page.getByText('target', { exact: true })).toHaveCount(0);
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Repository path').fill(resolve('..', 'examples', 'commerce'));
  await page.route('**/api/analysis/changes', route => route.abort('failed'));
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByRole('alert')).toContainText('Cannot reach the GraphScope API');
  await page.getByRole('button', { name: 'Stored snapshot investigation' }).click();
  await expect(page.getByLabel('Investigation question')).toHaveValue('');
  await expect(page.getByLabel('Investigation target')).toHaveValue('');
});

test('local algorithms repository produces its own impact graph', async ({ page }) => {
  const root = resolve('..', 'cloned_repos', 'algorithms');
  test.skip(!existsSync(root), 'Optional local repository fixture');
  await page.goto('/');
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Analysis mode').selectOption('impact');
  await analysis.getByLabel('Repository path').fill(root);
  await analysis.getByLabel('Qualified targets').fill('algorithms.math.goldbach.goldbach');
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByLabel('Analysis summary').getByText('10', { exact: true })).toBeVisible();
  await expect(analysis.locator('.graph-node')).toHaveCount(10);
  await expect(analysis.getByText('Results for ' + root, { exact: true })).toBeVisible();
  await expect(page.getByLabel('Investigation question')).toHaveCount(0);
});


test('Click graph labels stay within cards and the workspace responds to mobile', async ({ page }) => {
  const root = resolve('..', 'cloned_repos', 'click');
  test.skip(!existsSync(root), 'Optional local repository fixture');
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto('/');
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Analysis mode').selectOption('impact');
  await analysis.getByLabel('Repository path').fill(root);
  await analysis.getByLabel('Qualified targets').fill('click._compat.term_len');
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.locator('.graph-node').first()).toBeVisible();
  expect(await analysis.locator('.node-label').evaluateAll(labels => labels.every(label => getComputedStyle(label).overflow === 'hidden' && getComputedStyle(label).textOverflow === 'ellipsis'))).toBeTruthy();
  await page.screenshot({ path: '../reports/ui-desktop.png', fullPage: true });
  await analysis.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(analysis.locator('.canvas-toolbar')).toContainText('130%');
  await analysis.getByRole('button', { name: 'Fit graph', exact: true }).click();
  await expect(analysis.locator('.canvas-toolbar')).toContainText('100%');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(analysis.getByLabel('Repository path')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await analysis.locator('.analysis-graph').scrollIntoViewIfNeeded();
  await page.screenshot({ path: '../reports/ui-mobile.png', fullPage: true });
});


test('model suggestion consent, candidate review, and real confirmed impact', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Describe a change' }).click();
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Repository path').fill(resolve('..', 'examples', 'commerce'));
  await analysis.getByLabel('Suggestion provider').selectOption('gemini');
  await analysis.getByLabel('Describe the proposed change').fill('Reject orders with insufficient inventory');
  await expect(analysis.getByRole('button', { name: 'Analyze repository' })).toBeDisabled();
  await analysis.getByLabel('Allow sending').check();
  let modelRequests = 0;
  await page.route('**/api/analysis/propose', async route => {
    const request = route.request().postDataJSON();
    if (request.provider === 'gemini') {
      modelRequests++;
      expect(request.share_catalog).toBe(true);
      expect(request.confirm).toBe(false);
      await route.fulfill({ json: { status: 'confirmation_required', provider: 'gemini', candidates: [{ id: 'suggested', qualified_name: 'inventory.validate_stock' }], suggestions: ['Review quantity boundaries'] } });
    } else {
      expect(request.confirm).toBe(true);
      expect(request.targets).toEqual(['inventory.validate_stock']);
      await route.continue();
    }
  });
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByLabel('Proposal review')).toContainText('No blast radius has been calculated yet');
  await expect(analysis.getByLabel('Analysis summary')).toHaveCount(0);
  await analysis.getByRole('button', { name: 'Use inventory.validate_stock' }).click();
  await analysis.getByLabel('I confirm the explicit targets').check();
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByLabel('Analysis summary')).toBeVisible();
  await analysis.getByText('Affected functions and endpoints', { exact: true }).click();
  await expect(analysis.getByText('POST /orders', { exact: true }).last()).toBeVisible();
  expect(modelRequests).toBe(1);
});

test('provider failure offers a working offline fallback', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Describe a change' }).click();
  const analysis = page.getByRole('region', { name: 'Repository change analysis' });
  await analysis.getByLabel('Repository path').fill(resolve('..', 'examples', 'commerce'));
  await analysis.getByLabel('Suggestion provider').selectOption('ollama');
  await analysis.getByLabel('Describe the proposed change').fill('Change validate_stock');
  await analysis.getByLabel('Allow sending').check();
  await page.route('**/api/analysis/propose', async route => {
    if (route.request().postDataJSON().provider === 'ollama') await route.fulfill({ status: 502, json: { detail: 'Model suggestion failed: Provider unavailable. Use offline suggestions or explicit targets.' } });
    else await route.continue();
  });
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByRole('alert')).toContainText('Provider unavailable');
  await analysis.getByRole('button', { name: 'Use offline suggestions' }).click();
  await expect(analysis.getByLabel('Suggestion provider')).toHaveValue('none');
  await analysis.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(analysis.getByRole('button', { name: 'Use inventory.validate_stock' })).toBeVisible();
});
