// FIFO round-trip extraction from a run's fills: buy lots queue up and
// sells consume the oldest lots, producing holding periods for the
// position-cycle view.

import type { Fill } from "../../types";

export interface RoundTrip {
  symbol: string;
  openTs: string;
  closeTs: string;
  quantity: number;
  openPrice: number;
  closePrice: number;
  fees: number;
  pnl: number | null;
}

interface OpenLot {
  ts: string;
  price: number;
  quantity: number;
  feePerUnit: number;
}

function sortedFills(fills: Fill[]): Fill[] {
  return [...fills].sort((a, b) => a.seq - b.seq);
}

/** Match buys and sells FIFO per symbol. Sells that exceed open quantity
 * (should not happen in a sane archive) close what they can; the residue
 * is ignored and reported by the caller's honesty note when counts differ. */
export function roundTrips(fills: Fill[]): RoundTrip[] {
  const queues = new Map<string, OpenLot[]>();
  const trips: RoundTrip[] = [];
  for (const fill of sortedFills(fills)) {
    if (fill.side !== "buy" && fill.side !== "sell") continue;
    if (fill.price === null || fill.price === undefined) continue;
    const qty = fill.quantity ?? 0;
    if (qty <= 0) continue;
    const fees = fill.fees_total ?? 0;
    const queue = queues.get(fill.symbol) ?? [];
    queues.set(fill.symbol, queue);
    if (fill.side === "buy") {
      queue.push({
        ts: fill.ts,
        price: fill.price,
        quantity: qty,
        feePerUnit: fees / qty,
      });
      continue;
    }
    let remaining = qty;
    while (remaining > 0 && queue.length > 0) {
      const lot = queue[0];
      const take = Math.min(lot.quantity, remaining);
      const openFees = take * lot.feePerUnit;
      const sellFeePerUnit = fees / qty;
      trips.push({
        symbol: fill.symbol,
        openTs: lot.ts,
        closeTs: fill.ts,
        quantity: take,
        openPrice: lot.price,
        closePrice: fill.price,
        fees: openFees + take * sellFeePerUnit,
        pnl: (fill.price - lot.price) * take - openFees - take * sellFeePerUnit,
      });
      lot.quantity -= take;
      remaining -= take;
      if (lot.quantity <= 0) queue.shift();
    }
  }
  return trips;
}

/** Lots still open at the end of the run (no closing sell). */
export function openInterest(fills: Fill[]): { symbol: string; quantity: number; openTs: string }[] {
  const queues = new Map<string, OpenLot[]>();
  for (const fill of sortedFills(fills)) {
    if (fill.side !== "buy" && fill.side !== "sell") continue;
    if (fill.price === null || fill.price === undefined) continue;
    const qty = fill.quantity ?? 0;
    if (qty <= 0) continue;
    const queue = queues.get(fill.symbol) ?? [];
    queues.set(fill.symbol, queue);
    if (fill.side === "buy") {
      queue.push({ ts: fill.ts, price: fill.price, quantity: qty, feePerUnit: 0 });
    } else {
      let remaining = qty;
      while (remaining > 0 && queue.length > 0) {
        const take = Math.min(queue[0].quantity, remaining);
        queue[0].quantity -= take;
        remaining -= take;
        if (queue[0].quantity <= 0) queue.shift();
      }
    }
  }
  const out: { symbol: string; quantity: number; openTs: string }[] = [];
  for (const [symbol, lots] of queues) {
    for (const lot of lots) {
      out.push({ symbol, quantity: lot.quantity, openTs: lot.ts });
    }
  }
  return out;
}
