import styles from './LocationSelectMessage.module.css'

function LocationButtons({ children, isActive, isStreaming, onSelect }) {
  return (
    <div className={styles.buttons}>
      {children.map(child => (
        <button
          key={child.uid}
          className={`${styles.btn} ${child.is_home ? styles.homeBtn : ''}`}
          disabled={!isActive || isStreaming}
          onClick={() => onSelect?.(child.uid, child.name)}
        >
          <span className={styles.btnBody}>
            <span className={styles.btnName}>{child.name}</span>
            {(child.type_display || child.state_name) && (
              <span className={styles.btnMeta}>
                {child.type_display && <span className={styles.btnType}>{child.type_display}</span>}
                {child.type_display && child.state_name && <span className={styles.btnMetaSep}>·</span>}
                {child.state_name && <span className={styles.btnState}>{child.state_name}</span>}
              </span>
            )}
          </span>
          {child.is_home && <span className={styles.homeTag}>дом</span>}
        </button>
      ))}
    </div>
  )
}

export function LocationSelectMessage({ data, isActive, isStreaming, onSelect }) {
  const { parent, children } = data
  const heading = parent
    ? `Выберите место в ${parent.name}:`
    : 'Выберите локацию:'

  return (
    <div className={styles.root}>
      <p className={styles.heading}>{heading}</p>
      <LocationButtons
        children={children}
        isActive={isActive}
        isStreaming={isStreaming}
        onSelect={onSelect}
      />
    </div>
  )
}

export function SceneReadyMessage({ data }) {
  const { location } = data
  return (
    <div className={styles.sceneReady}>
      <span className={styles.sceneLabel}>Сцена создана</span>
      <p className={styles.sceneName}>{location.name}</p>
      {location.description && (
        <p className={styles.sceneDesc}>{location.description}</p>
      )}
    </div>
  )
}
