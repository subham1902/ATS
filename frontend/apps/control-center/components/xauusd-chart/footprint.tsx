import type { Footprint } from "./useMetaTraderFeed";
export function FootprintProxy({ data }: { data: Footprint | null }) {
  return (
    <section>
      <h2>Broker tick footprint proxy</h2>
      <p>BROKER_TICK_PROXY · quote observations, not a global exchange tape.</p>
      <p>
        Direction: inferred price changes · {data?.inference_method ?? "N/A"}. Executed buy/sell volume and order-book
        imbalance: N/A.
      </p>
      {data?.reason && <p>{data.reason}</p>}
      <table>
        <thead>
          <tr>
            <th>Price</th>
            <th>Observed ticks</th>
            <th>Inferred up</th>
            <th>Inferred down</th>
          </tr>
        </thead>
        <tbody>
          {data?.levels.map((level) => (
            <tr key={level.price}>
              <td>{level.price}</td>
              <td>{level.tick_count}</td>
              <td>{level.up_ticks}</td>
              <td>{level.down_ticks}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
