import React from "react";
import styled from "styled-components";
import { Cell } from "components/SimpleTableComponents";
import { CheckBox, RadioButton } from "components";

interface FieldRowProps {
  name: string;
  type: string;
  nullable?: boolean;
  destinationName: string;
  isPrimaryKey: boolean;
  isPrimaryKeyEnabled: boolean;
  isCursor: boolean;
  isCursorEnabled: boolean;
  depth?: number;

  onPrimaryKeyChange: () => void;
  onCursorChange: () => void;
}

const FirstCell = styled(Cell)<{ depth?: number }>`
  text-overflow: ellipsis;
  overflow: hidden;
  margin-left: ${({ depth }) => (depth ? depth * -38 : 0)}px;
`;

const NameContainer = styled.div<{ depth?: number }>`
  padding-left: ${({ depth }) => (depth ? depth * 59 : 0)}px;
`;

const LastCell = styled(Cell)<{ depth?: number }>`
  margin-right: ${({ depth }) => (depth ? depth * -38 : 0)}px;
`;

const RadiobuttonContainer = styled.div<{ depth?: number }>`
  padding-right: ${({ depth }) => (depth ? depth * 38 : 0)}px;
`;

const FieldRow: React.FC<FieldRowProps> = (props) => {
  return (
    <>
      <FirstCell depth={props.depth} flex={1.5}>
        <NameContainer depth={props.depth} title={props.name}>
          {props.name}
        </NameContainer>
      </FirstCell>
      <Cell />
      <Cell>
        {props.type}
        {props.nullable}
      </Cell>
      <Cell>{props.destinationName}</Cell>
      <Cell flex={1.5} />
      <Cell>
        <CheckBox checked={props.isPrimaryKey} />
      </Cell>
      <LastCell depth={props.depth}>
        <RadiobuttonContainer depth={props.depth}>
          <RadioButton checked={props.isCursor} />
        </RadiobuttonContainer>
      </LastCell>
    </>
  );
};

export { FieldRow };
