import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable } from "./Table";
import { csvCell, dayBoundary } from "./lib";
import { SectionHeading, TimeRange } from "./components";
import { useState } from "react";
import { ActivityLogs } from "./Views";
import type { Snapshot } from "./types";

describe("dashboard table QoL", () => {
  it("keeps explanations hidden until help is focused and closes them with Escape", async () => {
    const user = userEvent.setup();
    render(
      <SectionHeading
        title="Recovery"
        caption="Only Twitch confirmation counts as success."
      />,
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.tab();
    expect(
      screen.getByRole("button", { name: "About Recovery" }),
    ).toHaveFocus();
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "Only Twitch confirmation counts as success.",
    );
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
  it("pauses log following without clearing records or starting another request", async () => {
    const fetcher = vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("logs?")
          ? {
              lines: [
                {
                  level: "INFO",
                  message: "Keep this record",
                  at: "01/11/26 10:00:00",
                },
              ],
              cursor: "saved",
            }
          : [],
    }));
    vi.stubGlobal("fetch", fetcher);
    try {
      const user = userEvent.setup();
      render(
        <ActivityLogs
          data={
            {
              channels: [],
              timezone: "Europe/Budapest",
              generated_at: 1,
            } as unknown as Snapshot
          }
        />,
      );
      await user.click(screen.getByRole("button", { name: "Logs" }));
      await screen.findByText("Keep this record");
      const count = fetcher.mock.calls.length;
      await user.click(screen.getByRole("button", { name: "Pause following" }));
      expect(screen.getByText("Keep this record")).toBeInTheDocument();
      expect(fetcher.mock.calls.length).toBe(count);
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("uses the configured timezone across 23-hour and 25-hour days", () => {
    expect(
      dayBoundary("2026-03-29", "Europe/Budapest", true) -
        dayBoundary("2026-03-29") +
        1,
    ).toBe(23 * 3600);
    expect(
      dayBoundary("2026-10-25", "Europe/Budapest", true) -
        dayBoundary("2026-10-25") +
        1,
    ).toBe(25 * 3600);
  });
  it("sorts points as numbers, searches, and restores a saved view", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        account="test"
        name="channels"
        rows={[
          { channel: "low", points: 20 },
          { channel: "high", points: 1000 },
        ]}
        columns={[
          { accessorKey: "channel", header: "Channel" },
          { accessorKey: "points", header: "Points" },
        ]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Points" }));
    expect(
      within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0],
    ).toHaveTextContent("high");
    await user.type(
      screen.getByRole("textbox", { name: "Search channels" }),
      "low",
    );
    expect(screen.queryByText("high")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Columns & views/ }));
    await user.type(
      screen.getByRole("textbox", { name: "View name" }),
      "Only low",
    );
    await user.click(screen.getByRole("button", { name: "Save view" }));
    await user.click(
      screen.getByRole("button", { name: "Reset table layout" }),
    );
    expect(screen.getByText("high")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Only low" }));
    expect(screen.queryByText("high")).not.toBeInTheDocument();
    expect(
      JSON.parse(localStorage.getItem("miner:test:channels:views")!)[0].name,
    ).toBe("Only low");
  });
  it("hides columns without mutating row data", async () => {
    const user = userEvent.setup(),
      rows = [{ channel: "2okos", points: 52093 }];
    render(
      <DataTable
        account="test"
        name="channels"
        rows={rows}
        columns={[
          { accessorKey: "channel", header: "Channel" },
          { accessorKey: "points", header: "Points" },
        ]}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Columns & views/ }));
    await user.click(screen.getByRole("checkbox", { name: "Points" }));
    expect(
      screen.queryByRole("columnheader", { name: "Points" }),
    ).not.toBeInTheDocument();
    expect(rows[0].points).toBe(52093);
  });
  it("exports safe CSV text while preserving negative numeric results", () => {
    expect(csvCell('=HYPERLINK("evil")')).toContain("'=HYPERLINK");
    expect(csvCell("@everyone")).toBe('"\'@everyone"');
    expect(csvCell(-5000)).toBe('"-5000"');
  });
  it("keeps a valid range when switching to custom dates", async () => {
    function Range() {
      const [value, set] = useState({
        start: 1700000000,
        end: 1700086400,
        preset: "7",
      });
      return (
        <>
          <TimeRange value={value} onChange={set} />
          <output>{String(Number.isFinite(value.start))}</output>
        </>
      );
    }
    const user = userEvent.setup();
    render(<Range />);
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Date range" }),
      "custom",
    );
    expect(screen.getByRole("status")).toHaveTextContent("true");
    expect(screen.getByLabelText("Start date")).toBeInTheDocument();
  });
});
