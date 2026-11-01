import { test, expect } from "@playwright/test";

test("navigates all observation pages without browser errors or external assets", async ({
  page,
}) => {
  const errors: string[] = [],
    external: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (!r.url().startsWith("http://127.0.0.1:5001")) external.push(r.url());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Everything in view." }),
  ).toBeVisible();
  for (const name of [
    "Channels",
    "Streaks & recovery",
    "Drops & rewards",
    "Predictions",
    "Activity & logs",
    "System",
  ]) {
    await page
      .getByRole("navigation")
      .getByRole("button", { name, exact: true })
      .click();
    await expect(page.locator("main")).toBeVisible();
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("filters, saves views, opens channel history and supports keyboard closing", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Channels", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Search channels" }).fill("2okos");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "2okos", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Channel balance" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: /Columns & views/ }).click();
  await page.getByRole("textbox", { name: "View name" }).fill("My channel");
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Search channels" }),
  ).toHaveValue("2okos");
  await expect(page.locator("tbody tr")).toHaveCount(1);
});

test("changes display preferences and fits narrow screens", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page
    .getByRole("combobox", { name: "Table density" })
    .selectOption("comfortable");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute(
    "data-density",
    "comfortable",
  );
  await page.setViewportSize({ width: 430, height: 900 });
  await expect(
    page.getByRole("button", { name: "Refresh all", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("only requests a refresh and shares that job across tabs", async ({
  page,
  context,
}) => {
  await page.goto("/");
  const second = await context.newPage();
  await second.goto("/");
  await page.getByRole("button", { name: "Refresh all", exact: true }).click();
  await expect(page.getByRole("button", { name: /Refreshing/ })).toBeDisabled();
  const firstState = await page.request
    .get("/api/v1/refresh")
    .then((r) => r.json());
  const secondState = await second.request
    .get("/api/v1/refresh")
    .then((r) => r.json());
  expect(firstState.id).toBe(secondState.id);
});

test("keeps the last received data on a connection failure", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Everything in view." }),
  ).toBeVisible();
  await page.route("**/api/v1/snapshot", (r) => r.abort());
  await expect(page.getByText("Connection to the miner was lost")).toBeVisible({
    timeout: 12000,
  });
  await expect(
    page.getByRole("heading", { name: "Everything in view." }),
  ).toBeVisible();
});
