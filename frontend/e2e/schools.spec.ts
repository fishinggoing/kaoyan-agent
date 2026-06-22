import { test, expect } from '@playwright/test'

test.describe('School Search Page', () => {
  test('displays school search page', async ({ page }) => {
    await page.goto('/schools')
    await expect(page.locator('h1')).toBeVisible()
  })
})

test.describe('Score Analysis Page', () => {
  test('displays score analysis page', async ({ page }) => {
    await page.goto('/scores')
    await expect(page.locator('h1')).toBeVisible()
  })
})
