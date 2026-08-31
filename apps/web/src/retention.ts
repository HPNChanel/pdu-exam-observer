export function parseRetentionEndDate(value: string, today = new Date()): { iso: string | null; error: string | null } {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  if (!match) return { iso: null, error: 'Nhập ngày theo định dạng dd/mm/yyyy.' };
  const [, dayText, monthText, yearText] = match;
  const day = Number(dayText); const month = Number(monthText); const year = Number(yearText);
  const candidate = new Date(year, month - 1, day);
  if (candidate.getFullYear() !== year || candidate.getMonth() !== month - 1 || candidate.getDate() !== day) return { iso: null, error: 'Ngày kết thúc lưu giữ không hợp lệ.' };
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (candidate < startOfToday) return { iso: null, error: 'Ngày kết thúc lưu giữ không được trước ngày hôm nay.' };
  return { iso: `${yearText}-${monthText}-${dayText}`, error: null };
}

export function formatRetentionEndDate(value: string) {
  const [year, month, day] = value.split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}
