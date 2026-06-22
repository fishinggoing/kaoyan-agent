import { test, expect } from '@playwright/test'

test.describe('Home Page', () => {
  test('displays app title and navigation', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('header')).toBeVisible()
    await expect(page.locator('text=GradSchool Advisor')).toBeVisible()
  })

  test('navigation links are present', async ({ page }) => {
    await page.goto('/')
    const nav = page.locator('nav')
    await expect(nav.getByText('首页')).toBeVisible()
    await expect(nav.getByText('院校查询')).toBeVisible()
    await expect(nav.getByText('分数线')).toBeVisible()
    await expect(nav.getByText('智能推荐')).toBeVisible()
  })
})

test.describe('Navigation', () => {
  test('can navigate to school search page', async ({ page }) => {
    await page.goto('/')
    await page.getByText('院校查询').first().click()
    await expect(page).toHaveURL(/\/schools/)
  })

  test('can navigate to score analysis page', async ({ page }) => {
    await page.goto('/')
    await page.getByText('分数线').first().click()
    await expect(page).toHaveURL(/\/scores/)
  })

  test('can navigate to decision page', async ({ page }) => {
    await page.goto('/')
    await page.getByText('智能推荐').first().click()
    await expect(page).toHaveURL(/\/decisions/)
  })
})
