import { test, expect } from '@playwright/test'

test.describe('Decision Page', () => {
  test('displays recommendation page with empty state', async ({ page }) => {
    await page.goto('/decisions')
    await expect(page.locator('h1')).toContainText('智能择校推荐')
  })

  test('shows configuration panel', async ({ page }) => {
    await page.goto('/decisions')
    await expect(page.locator('text=推荐设置')).toBeVisible()
    await expect(page.locator('text=开始智能推荐')).toBeVisible()
  })

  test('recommend button is disabled without profile', async ({ page }) => {
    await page.goto('/decisions')
    const btn = page.locator('button:has-text("开始智能推荐")')
    await expect(btn).toBeDisabled()
  })
})
