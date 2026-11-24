import * as THREE from 'three';

export interface InteractableBinding {
  object: THREE.Object3D;
  label: string | (() => string);
  onClick: () => void;
}

/**
 * Raycast hover & click interaction manager for studio monitors, ScreenBar light, and PC workstation.
 */
export class InteractableRegistry {
  private readonly bindings: InteractableBinding[] = [];
  private readonly raycaster = new THREE.Raycaster();
  private readonly pointer = new THREE.Vector2();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly domElement: HTMLElement;
  private readonly tooltipEl: HTMLElement;
  private readonly tooltipLabelEl: HTMLElement;

  private hovered: InteractableBinding | null = null;
  private pointerDownPos = { x: 0, y: 0 };
  private enabled = true;

  constructor(
    camera: THREE.PerspectiveCamera,
    domElement: HTMLElement,
    tooltipEl: HTMLElement,
    tooltipLabelEl: HTMLElement
  ) {
    this.camera = camera;
    this.domElement = domElement;
    this.tooltipEl = tooltipEl;
    this.tooltipLabelEl = tooltipLabelEl;

    domElement.addEventListener('pointermove', this.handleMove);
    domElement.addEventListener('pointerdown', this.handleDown);
    domElement.addEventListener('pointerup', this.handleUp);
    domElement.addEventListener('pointerleave', this.clearHover);
  }

  public clearHover = (): void => {
    this.hovered = null;
    this.tooltipEl.hidden = true;
    this.domElement.style.cursor = '';
  };

  public setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.clearHover();
    }
  }

  public register(binding: InteractableBinding): void {
    this.bindings.push(binding);
  }

  public dispose(): void {
    this.domElement.removeEventListener('pointermove', this.handleMove);
    this.domElement.removeEventListener('pointerdown', this.handleDown);
    this.domElement.removeEventListener('pointerup', this.handleUp);
    this.domElement.removeEventListener('pointerleave', this.clearHover);
  }

  private pick(clientX: number, clientY: number): InteractableBinding | null {
    if (!this.enabled || this.bindings.length === 0) return null;
    const rect = this.domElement.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);

    const targets = this.bindings.map((b) => b.object);
    const hits = this.raycaster.intersectObjects(targets, true);
    if (hits.length === 0) return null;

    let hitObj: THREE.Object3D | null = hits[0].object;
    while (hitObj) {
      const found = this.bindings.find((b) => b.object === hitObj);
      if (found) return found;
      hitObj = hitObj.parent;
    }
    return null;
  }

  private readonly handleMove = (e: PointerEvent): void => {
    const match = this.pick(e.clientX, e.clientY);
    this.hovered = match;
    if (match) {
      this.domElement.style.cursor = 'pointer';
      this.tooltipLabelEl.textContent = typeof match.label === 'function' ? match.label() : match.label;
      this.tooltipEl.style.left = `${e.clientX}px`;
      this.tooltipEl.style.top = `${e.clientY}px`;
      this.tooltipEl.hidden = false;
    } else {
      this.domElement.style.cursor = '';
      this.tooltipEl.hidden = true;
    }
  };

  private readonly handleDown = (e: PointerEvent): void => {
    this.pointerDownPos = { x: e.clientX, y: e.clientY };
  };

  private readonly handleUp = (e: PointerEvent): void => {
    if (!this.enabled || e.button !== 0) return;
    const dist = Math.hypot(e.clientX - this.pointerDownPos.x, e.clientY - this.pointerDownPos.y);
    if (dist > 6) return; // Ignore orbit drags
    const match = this.hovered ?? this.pick(e.clientX, e.clientY);
    if (match) {
      match.onClick();
      this.clearHover();
    }
  };
}
