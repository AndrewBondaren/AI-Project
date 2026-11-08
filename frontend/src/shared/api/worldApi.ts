import { api } from './client'

export const getWorlds = api.listWorlds
export const getCharacters = api.listCharacters
export const copyCharacter = api.copyCharacter
export const deleteCharacter = api.deleteCharacter
export const importWorld = api.importWorld
export const importCharacter = api.importCharacter
