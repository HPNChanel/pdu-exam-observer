import { parseRetentionEndDate } from './retention';
import { describe, expect, it } from 'vitest';

describe('Vietnamese retention date parser', () => {
  const today = new Date(2026, 7, 25);

  it('converts an explicit dd/mm/yyyy retention date on or after today to the backend ISO contract', () => {
    expect(parseRetentionEndDate('25/08/2026', today)).toEqual({ iso: '2026-08-25', error: null });
    expect(parseRetentionEndDate('31/12/2027', today)).toEqual({ iso: '2027-12-31', error: null });
  });

  it('rejects malformed, impossible, and past retention dates', () => {
    expect(parseRetentionEndDate('2027-12-31', today).error).toMatch(/dd\/mm\/yyyy/i);
    expect(parseRetentionEndDate('31/02/2027', today).error).toMatch(/không hợp lệ/i);
    expect(parseRetentionEndDate('24/08/2026', today).error).toMatch(/trước ngày hôm nay/i);
  });
});
