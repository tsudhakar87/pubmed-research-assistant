export function PaperSkeleton() {
  return (
    <div style={{ padding: '16px 0', borderBottom: '1px solid #dbd6c8' }}>
      <div className="skeleton" style={{ height: 16, width: '80%', marginBottom: 8 }} />
      <div className="skeleton" style={{ height: 10, width: '40%', marginBottom: 10 }} />
      <div className="skeleton" style={{ height: 11, width: '95%', marginBottom: 6 }} />
      <div className="skeleton" style={{ height: 11, width: '70%' }} />
    </div>
  );
}

export function RecentQueriesSkeleton() {
  return (
    <>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ padding: '9px 0', borderBottom: '1px solid #dbd6c8' }}>
          <div className="skeleton" style={{ height: 11, width: '90%', marginBottom: 4 }} />
          <div className="skeleton" style={{ height: 9, width: '40%' }} />
        </div>
      ))}
    </>
  );
}
