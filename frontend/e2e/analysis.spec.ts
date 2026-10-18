import { expect, test } from '@playwright/test';
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
