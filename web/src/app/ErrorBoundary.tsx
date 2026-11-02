import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "../components";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Do not log conversation content or credentials from render errors.
  }
  render() {
    if (this.state.failed)
      return (
        <>
          <ErrorState
            title="Esta vista no está disponible"
            message="No se ha podido mostrar el contenido. Puedes volver a intentarlo o ir a otra sección."
            retry={() => this.setState({ failed: false })}
          />
          <p>
            Si acabas de actualizar CitaLab, recarga para obtener la nueva
            versión. Guarda tus borradores antes: recargar descarta los cambios
            sin publicar.
          </p>
          <button type="button" onClick={() => window.location.reload()}>
            Recargar aplicación
          </button>
        </>
      );
    return this.props.children;
  }
}
