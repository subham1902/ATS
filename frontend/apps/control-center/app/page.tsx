import { LiveOverview } from "../components/overview/LiveOverview";
import { OperatorCockpitV2 } from "../components/cockpit/OperatorCockpitV2";

export default function Page() {
  return process.env.NEXT_PUBLIC_ATS_OPERATOR_COCKPIT_V2 === "1"
    ? <OperatorCockpitV2 />
    : <LiveOverview />;
}
