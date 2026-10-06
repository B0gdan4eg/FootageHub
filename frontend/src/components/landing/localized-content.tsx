"use client";

import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { translateText } from "@/lib/language";

export type LandingLanguage = "ru" | "en";

const TRANSLATABLE_ATTRIBUTES = ["alt", "aria-label", "placeholder", "title"] as const;

function localizeNode(node: ReactNode): ReactNode {
  if (typeof node === "string") return translateText(node);
  if (Array.isArray(node)) return Children.map(node, localizeNode);
  if (!isValidElement(node)) return node;

  const element = node as ReactElement<Record<string, unknown>>;
  const props: Record<string, unknown> = {};

  for (const attribute of TRANSLATABLE_ATTRIBUTES) {
    const value = element.props[attribute];
    if (typeof value === "string") props[attribute] = translateText(value);
  }

  if ("children" in element.props) {
    props.children = localizeNode(element.props.children as ReactNode);
  }

  return cloneElement(element, props);
}

export function LocalizedContent({
  children,
  language,
}: {
  children: ReactNode;
  language: LandingLanguage;
}) {
  return language === "en" ? localizeNode(children) : children;
}
