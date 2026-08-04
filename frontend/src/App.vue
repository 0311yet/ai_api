<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme } from 'naive-ui'

const themeOverrides = {
  common: {
    primaryColor: '#5ca48d',
    primaryColorHover: '#78bca5',
    primaryColorPressed: '#4b8975',
    errorColor: '#D03050',
    successColor: '#18A058',
    warningColor: '#F0A020',
    infoColor: '#2080F0',
    bodyColor: '#10141a',
    cardColor: '#1a2129',
    modalColor: '#1a2129',
    popoverColor: '#1a2129',
    tableColor: '#1a2129',
    inputColor: '#151b22',
    borderColor: '#2b3540',
    textColorBase: '#f3f6f7',
    textColor1: '#f3f6f7',
    textColor2: '#dbe4e7',
    textColor3: '#b4c0c7',
    textColorDisabled: '#8c8c8c',
    fontFamily: 'Inter, system-ui, sans-serif',
    fontFamilyMono: 'JetBrains Mono, monospace',
  },
  DataTable: {
    thColor: '#292935',
    tdColor: '#1f1e2a',
    borderColor: '#2e2e42',
    thTextColor: '#c0c7d4',
    tdTextColor: '#e3e0f1',
  },
  Button: {
    colorPrimary: '#409eff',
    colorHoverPrimary: '#66b1ff',
    colorPressedPrimary: '#3a8ee6',
    textColorPrimary: '#ffffff',
  },
  Input: {
    color: '#1f1e2a',
    colorFocus: '#1f1e2a',
    borderColor: '#2e2e42',
    borderColorFocus: '#409eff',
    textColor: '#ffffff',
    placeholderColor: '#8c8c8c',
  },
  Modal: {
    color: '#1f1e2a',
    textColor: '#ffffff',
  },
  Card: {
    color: '#1f1e2a',
    borderColor: '#2e2e42',
    textColor: '#ffffff',
  },
  Tag: {
    borderRadius: '9999px',
  },
  Pagination: {
    buttonColor: '#1f1e2a',
    buttonColorHover: '#292935',
  },
}
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="themeOverrides">
    <NMessageProvider>
      <NDialogProvider>
        <router-view />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
