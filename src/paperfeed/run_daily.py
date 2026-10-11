"""Compatibility entry point for older commands; PaperFeed now runs weekly."""

from paperfeed.run_weekly import (
    WeeklyRunResult as DailyRunResult,
    NoUsablePositiveSeedsError,
    build_parser,
    main,
    run_weekly as run_daily,
)

if __name__ == "__main__":
    raise SystemExit(main())
