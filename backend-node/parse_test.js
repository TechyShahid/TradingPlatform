const dateStrs = [
  "2026-02-19T18:30:00.000Z",
  "19-Feb-2026",
  "20-Feb-2026 16:00:00",
];

const months = {
  'Jan': 0, 'Feb': 1, 'Mar': 2, 'Apr': 3, 'May': 4, 'Jun': 5,
  'Jul': 6, 'Aug': 7, 'Sep': 8, 'Oct': 9, 'Nov': 10, 'Dec': 11
};

function parseNseDate(dateStr) {
  // If ISO 8601 string
  if (dateStr.includes('T')) {
    const d = new Date(dateStr);
    // We want the local day that this represents (in India)
    // Actually, getting fullYear() gives local TZ year. It's safer to extract components
    const year = d.getFullYear();
    const month = d.getMonth();
    const day = d.getDate();
    return Date.UTC(year, month, day) / 1000;
  }

  // Handle "19-Feb-2026" or "20-Feb-2026 16:00:00"
  const parts = dateStr.split(/[- ]/);
  if (parts.length >= 3) {
    const day = parseInt(parts[0]);
    const monthStr = parts[1];
    const year = parseInt(parts[2]);

    if (months[monthStr] !== undefined && !isNaN(day) && !isNaN(year)) {
      return Date.UTC(year, months[monthStr], day) / 1000;
    }
  }

  // Fallback
  return new Date(dateStr).getTime() / 1000;
}

dateStrs.forEach(d => {
  const t = parseNseDate(d);
  console.log(`${d} -> ${t} -> ${new Date(t * 1000).toUTCString()}`);
});
