import type { TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";
import { RecordedRun } from "@/components/RecordedRun";

export function StepNight({ data }: { data: TourData }) {
  if (!data.featuredNight) {
    return <Empty>This recording has no featured run to replay.</Empty>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--color-text-dim)]">
        Track {data.featuredNight.track}, night {data.featuredNight.night}. Watch it play: each line below is the
        engine&apos;s own record of a candidate it proposed, trained and measured, unattended, on this project&apos;s own
        machine.
      </p>
      <RecordedRun />
    </div>
  );
}
