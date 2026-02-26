interface Props {
  message?: string;
}

export function LoadingSpinner({ message = "Loading..." }: Props) {
  return (
    <div className="loading-spinner">
      <div className="spinner" />
      <p>{message}</p>
    </div>
  );
}
